"""
Web interface.
"""
import gc
import uos
import uasyncio

from microdot_asyncio import Microdot, Response, send_file
import ulogging as logging

from config import conf, updateConf, getByDotKey

# This is used to look up a content type from a file extension for the static
# file server.
MIME_TYPES = {
        'html': 'text/html; charset=UTF-8',
        'css': 'text/css; charset=UTF-8',
        'js': 'application/javascript',
}

# This is the subset of the main config file that we allow to be managed via
# the web API
conf_subset = {
    'valve.ppl': ['Pulses/L', getByDotKey('valve.ppl')],
    'valve.max_flow_period': ['Max Flow Secs', getByDotKey('valve.max_flow_period')],
    'valve.max_flow_delay': ['Off Delay Secs', getByDotKey('valve.max_flow_delay')],
    'valve.max_flow_warn': ['Warn At Secs', getByDotKey('valve.max_flow_warn')],
    #'sensor_id': ['Sensor ID', getByDotKey('sensor_id')],
    'mqtt.enabled': ['MQTT Enabled', getByDotKey('mqtt.enabled')],
    'mqtt.host': ['MQTT Host', getByDotKey('mqtt.host')],
    'ota_url': ['OTA URL', getByDotKey('ota_url')],
}


# The main web app. On main app startup in main.py, after the hexapod instance has been
# created, and this web app has been imported, the hexapod instance will be
# added to the web app on the hexapod attribute.
# This will allow the web app to get access to the hexapod via the attribute:
# `request.app.hexapod` in all request handlers.
app = Microdot()

async def reboot(wait=2, hard=False):
    """
    Coro that can be called to perform a reboot after `wait` seconds.

    This is helpful where the reboot is initiated from a web interface or
    some other external trigger, but feedback needs to be given first before
    initiating the reboot.

    Args:
        wait (int): Seconds to wait before rebooting
        hard (bool): If true, then a machine.reset() is performed which is
            equivalent to pressing the reset button. If False, a soft reboot is
            performed by simply exiting the main process which will cause a
            Python reset by reloading from boot.py again.
            The hard reset is helpful if WiFi needs to be reset too, for
            example.
    """
    #pylint: disable=import-outside-toplevel

    logging.info("Going to reboot in %s secs...", wait)

    await uasyncio.sleep(wait)

    # Hard reboot?
    if hard:
        import machine
        machine.reset()

    # This is a soft reboot
    import sys
    sys.exit()

def staticFile(path, content_type=None, gzipped=True):
    """
    General function returning static files and ensuring the content type is
    set correctly.

    All static files are also expected to be gzipped, so we force the
    Content-Encoding header to gzip here.

    Args:
        path (str): full path to the static file. The content type will be set
            based on the file name extension, so make sure the static files
            have and extension that can be used to derive the content type.
        content_type (str): The `Content-Type` header to use in the response.
            If omitted, it is generated automatically from the file extension.
        gzipped (bool): If the file being sent is gzipped set this to True to set
            the `Content-Encoding` header to gzip. This is the default since
            all static files are gzipped, although the file name does not have
            .gz or similar extension.
            For files that are not gzipped, set this to False.

    Returns:
        A Response object ready to be returned to the web server.
    """
    gc.collect()
    # Call Microdot's send_file to create the Response object for the file.
    stat_f = send_file(path, content_type=content_type)
    if gzipped:
        stat_f.headers['Content-Encoding'] = 'gzip'
    return stat_f

@app.route('/')
async def index(request):
    """
    Web interface main entry point. We simply serve the index.html from here.
    """
    # pylint: disable=unused-argument
    gc.collect()
    logging.debug("Web request: index")
    return staticFile('static/index.html')

@app.route('/static/<stat_file>')
async def static(request, stat_file):
    """
    Static files handler
    """
    # pylint: disable=unused-argument
    logging.debug("Web request: static file: %s", stat_file)
    return staticFile(f'static/{stat_file}')

@app.route('/get_params')
async def getParams(request):
    """
    Endpoint to return the current hexapod parameters and values as a JSON
    structure.

    GET Response:
    {
        "servo": {
            "mid": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            },
            "left": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            },
            "right": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            }
        },
        "paused": (bool),
        "period": (int),
        "speed": (float),   # Period as a % of min and max periods
    }
    """
    return request.app.hexapod.getParams()

@app.route('/set_params', methods=["POST"])
async def setParams(request):
    """
    Endpoint to set one or more hexapod runtime parameters.

    All entries are optional, but if nested values are supplied, they must be
    contained in their proper hierarchy. For example if only only the right
    servo trim is to be set the JSON post data should be:

    {
        "servo": {
            "right": {
                "trim": 2
            }
        }
    }

    POST JSON data:
    {
        "servo": {
            "mid": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            },
            "left": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            },
            "right": {
                "amplitude": (int),
                "phase_shift": (int),
                "trim": (int)
            }
        },
        "paused": (bool),
        "period": (int),
        "speed": (float),   # Period as a % of min and max periods
    }
    """
    #pylint: disable=too-many-branches
    errs = []
    for key, val in request.json.items():
        if key == 'paused':
            request.app.hexapod.pause = val
            continue

        if key == 'period':
            res = request.app.hexapod.setPeriod(int(val))
            if res:
                errs.append(res)
            continue

        if key == "speed":
            try:
                request.app.hexapod.speed = val
            except ValueError as res:
                errs.append(res)
            continue

        if key == "servo":
            hpod = request.app.hexapod
            for servo, params in val.items():
                if not servo in hpod.servos:
                    errs.append(f"No servo named: {servo}")
                    continue
                for pkey, pval in params.items():
                    if not pkey in ['amplitude', 'phase_shift', 'trim']:
                        errs.append(f"Invalid param for servo {servo}: {pkey}")
                        continue
                    setattr(hpod.servos[servo], pkey, pval)
            continue

        errs.append(f"Invalid param to set: {key}")

    return {"errors": errs}

@app.route('/center')
async def centerServos(request):
    """
    Sets all servos to the center position (90°)
    """
    request.app.hexapod.centerServos()
    return {"errors": []}

@app.route('/pause', methods=["GET", "POST"])
async def pause(request):
    """
    Gets or sets the pause state.

    GET:
        Returns the current pause state as:
            {"paused": bool}

    POST:
        Set the pause state with this data structure:
            {"paused": bool} - true to pause, false to unpause
    """
    if request.method == "GET":
        return {"paused": request.app.hexapod.pause}

    # Must be a POST
    if not "paused" in request.json:
        return {"errors": ["Requires 'paused' key and bool state to set pause state."]}

    request.app.hexapod.pause = request.json['paused']

    return {"errors": []}

@app.route('/mem')
async def memInfo(_):
    """
    Returns the current memory status.

    GET:
        Returns:
            {"alloc": int, "free": int}
    """
    return {"alloc": gc.mem_alloc(), "free": gc.mem_free()}

async def runserver(host='0.0.0.0', port=80, debug=True):
    """
    Start the webserver.
    """
    logging.info("Starting web server on %s:%s", host, port)
    await app.start_server(host=host, port=port, debug=debug)
