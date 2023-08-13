"""
Hexapod Web API module.

This module imports the web app from the webserver module and then extends the
main app with all the API endpoints exposed for the Hexapod.
"""
from webserver import gc, app, logging
from webserver import runserver # Convenience import for main @pylint: disable=unused-import
from microdot_asyncio_websocket import with_websocket
from ws_controller import uasyncio, ping, obstacleReporter
from version import VERSION

#pylint: disable=broad-except

@app.before_request
async def requestHook(request):
    """
    Hook that is called before every request.

    This is helpful to log the request details for all requests.
    """
    logging.info(
        "HTTP: %s %s, Args: %s, JSON: %s",
        request.method,
        request.path,
        request.args,
        request.json
    )
    gc.collect()

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
    return request.app.hexapod.params

@app.route('/pause', methods=["POST"])
async def pause(request):
    """
    Pauses the hexapod if it is currently running

    POST:
        An empty body
    """
    request.app.hexapod.pause = True

@app.route('/run', methods=["POST"])
async def run(request):
    """
    Starts or unpauses the hexapod if it was paused.

    POST:
        An empty body
    """
    request.app.hexapod.pause = False

@app.route('/trim', methods=["GET", "POST"])
async def trim(request):
    """
    Gets or sets the servo trim values.

    GET:
        Returns the current trim values as:
            [left trim, mid trim, right trim]

    POST request data:
        A list with the trim values for the servos:
            [left trim, mid trim, right trim]
        Any of the 3 trim values can be None (null) to not set the trim for
        that servo.
        Optionally, this could also be a JSON object with a 'trim' keyword and
        value the list of trim settings, and an optional 'center' boolean:
            {
                "trim": [left trim, mid trim, right trim],
                "center": True/False # If true, servos will also be centered
                            with new trim values.
            }

    POST response:
        If no errors, returns the same as for the GET request.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return request.app.hexapod.trim

    # By default we do not also center servos
    center = False

    # Must be a POST, body could be a list or dict
    trim_list = request.json
    # If it's a dict, we expect the 'trim' key, from which we will then take
    # the value which is expected to the trim list.
    if isinstance(trim_list, dict):
        if not "trim" in trim_list:
            return {"errors": ["No 'trim' key in parameters."]}
        # Before changing trim_list from a dict to the actual trim values, get
        # the center value out if any
        center = trim_list.get("center", False)
        trim_list = trim_list['trim']

    if not isinstance(trim_list, list) or len(trim_list) != 3:
        return {"errors": ["Expect a list of three trim values."]}

    request.app.hexapod.trim = trim_list

    # Do we also center?
    if center:
        request.app.hexapod.centerServos(True)

    return request.app.hexapod.trim

@app.route('/center_servos', methods=["POST"])
async def centerServos(request):
    """
    Sets all servos to the center position (90°), with or without the current
    trim settings.

    NOTE: This will force the paused state if not already paused.

    POST request data:
        "with_trim": boolean

    The post data is optional and if not supplied, "with_trim" will default to
    True, meaning that the current trim settings will be taken into account
    when centering the servos.

    POST response:
        {errors": [One or more error strings if error]}
    """
    resp = {"errors": []}
    try:
        with_trim = request.json.get("with_trim", True) if request.json else True
        request.app.hexapod.centerServos(with_trim)
    except Exception as exc:
        resp["errors"] = [f"Application error: {exc}"]

    return resp

@app.route('/steer', methods=["GET", "POST"])
async def steer(request):
    """
    Gets or sets the steering direction.

    GET:
        Returns the current steering values as:
            {
                'dir': one of 'fwd', 'rev', 'rotr', 'rotl'
                'angle': current angle off the direction
            }

    POST request data:
        {
            'dir': 'fwd', 'rev', 'rotr', 'rotl'
            'angle': angle off the 'fwd' or 'rev' direction
        }

        Both `dir` and `angle` are optional. Angle will be ignored if the
        current direction is not 'fwd' or 'rev'.

    POST response:
        If no errors, returns the same as for the GET request.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return request.app.hexapod.steer

    # Must be a POST, body could be a list or dict
    params = request.json
    if not ('dir' in params or 'angle' in params):
        return {"errors": ["At least one of 'dir' or 'angle' keys required."]}

    try:
        request.app.hexapod.steer = params
    except Exception as exc:
        return {"errors": [str(exc)]}

    return request.app.hexapod.steer

@app.route('/speed', methods=["GET", "POST"])
async def speed(request):
    """
    Gets or sets the oscillation speed, or period.

    GET:
        Returns the current speed value as a percentage of the total allowed
        period:
        {"speed": speed percentage as integer (0 - 100)"

    POST request data:
        {"speed": speed percentage as integer (0 - 100)"

    POST response:
        If no errors, returns the same as for the GET request. Note that the
        speed percentage returned could be slightly different to the value used
        to set it. This is due to rounding errors when sticking to integer
        percentages.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return {"speed": request.app.hexapod.speed}

    # Must be a POST, body could be a list or dict
    dat = request.json
    # We expect the 'speed' key, from which we will then take
    # the actual speed value
    if isinstance(dat, dict):
        if not "speed" in dat:
            return {"errors": ["No 'speed' key in parameters."]}

    dat = dat["speed"]

    # Allow it to be passed in as a string
    if isinstance(dat, str):
        try:
            dat = int(dat)
        except ValueError as exc:
            return {"errors": [str(exc)]}

    try:
        request.app.hexapod.speed = dat
    except Exception as exc:
        return {"errors": [str(exc)]}

    return {"speed": request.app.hexapod.speed}

@app.route('/stroke', methods=["GET", "POST"])
async def stroke(request):
    """
    Gets or sets the oscillation amplitude for the left and right legs as a
    a percentage of the max stroke defined for them.

    GET:
        Returns the current stroke value as a percentage of the maximum allowed
        stroke or amplitude setting for the left/right legs:
        {"stroke": stroke percentage as integer (0 - 100)"

    POST request data:
        {"stroke": stroke percentage as integer (0 - 100)"

    POST response:
        If no errors, returns the same as for the GET request. Note that the
        stroke percentage returned could be slightly different to the value used
        to set it. This is due to rounding errors when sticking to integer
        percentages.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return {"stroke": request.app.hexapod.stroke}

    # Must be a POST, body could be a list or dict
    dat = request.json
    # We expect the 'stroke' key, from which we will then take
    # the actual stroke value
    if isinstance(dat, dict):
        if not "stroke" in dat:
            return {"errors": ["No 'stroke' key in parameters."]}

    try:
        request.app.hexapod.stroke = dat['stroke']
    except Exception as exc:
        return {"errors": [exc]}

    return {"stroke": request.app.hexapod.stroke}

def handleTrim(val, hexapod):
    """
    Handles a request to query or set the servo trim values.

    For just getting the current trim values, val will be None, otherwise it is
    expected to be a string like:
        left:mid:right[:center]

    ...where each field is a trim value as integer angle, and the optional center
    field is either "true" or "false".

    If this is all is good, this function will set the servo trims and
    optionally center the them, unless val was None, in which case only the
    current trim values will be returned.

    Args:
        val (str|None): See above
        hexapod (inst): Instance of the hexapod

    Returns:
        On successful setting the trims or when only requesting the current
        values, returns a string:
            "left:mid:right"

        On error, returns a string:
            "err:The error message"
    """
    # Preset the response so we can test if was already set to an error later
    resp = None

    # Needs to set trims?
    if val is not None:
        logging.info("Setting trims: %s", val)
        # Split on colons and check for the correct number of items
        vals = val.split(':')
        if len(vals) not in [3, 4]:
            return f"err:Invalid trim values: {val}"

        # Pop the center element off if present, else default to false
        cent = vals.pop() if len(vals) == 4 else 'false'
        if cent not in ['true', 'false']:
            return f"err:Invalid trim center value: {cent}"
        # Make the center value a boolean
        cent = cent == 'true'

        # Try convert the trims to ints
        try:
            vals = [int(v) for v in vals]
        except ValueError:
            return f"err:One or more trim values are not integers: {vals}"
        # Set the trims
        hexapod.trim = vals
        # Do we also center?
        if cent:
            hexapod.centerServos(True)
    else:
        logging.info("Requesting current trim settings.")

    # Now set a response if we have not done so already
    if resp is None:
        # Need to convert the integers to strings before joining with a
        # string
        resp = ":".join([str(t) for t in hexapod.trim])

    return resp

@app.route('/ws')
@with_websocket
async def websock(request, ws):
    """
    Websocket handler.

    This handler is called as soon as the browser opens the /ws path to
    establish the websocket connection.

    When this happens, this function will be run as coro until the connection
    is closed.

    Args:
        _ : The request object. Unused in this case
        ws (socket): The websocket instance.
    """
    hexapod = request.app.hexapod

    # Create the tasks
    uasyncio.create_task(ping(ws))
    uasyncio.create_task(obstacleReporter(hexapod, ws))

    while True:
        # Wait for a message and then split iton the first colon into action
        # and arguments
        data = await ws.receive()
        data = data.split(':', 1)
        # All actions do not always have arguments, so work out what the action
        # and args are. No args will result in args == None
        if len(data) == 1:
            action = data[0]
            args = None
        else:
            action, args = data
        logging.debug(f"[WS]: Received: action: {action}, args: {args}")

        # What to do?
        response = None
        if action == 'version':
            response = f"version:{VERSION}"
        if action == 'memory':
            response = f"memory:{gc.mem_alloc()}:{gc.mem_free()}"
        if action == 'pong':
            logging.info("Received pong...")
        if action == 'trim':
            logging.info(f"Received trim:{args}...")
            response = f"trim:{handleTrim(args, hexapod)}"
        else:
            logging.info(f"Unhandled action: {action}")

        # Any response?
        if response:
            await ws.send(response)
