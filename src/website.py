"""
Web interface.
"""
from webserver import gc, app, logging, runserver

#pylint: disable=broad-except

@app.before_request
async def request_hook(request):
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
    gc.collect()
    return request.app.hexapod.params

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
    gc.collect()
    if request.method == "GET":
        return {"paused": request.app.hexapod.pause}

    # Must be a POST
    if not "paused" in request.json:
        return {"errors": ["Requires 'paused' key and bool state to set pause state."]}

    request.app.hexapod.pause = request.json['paused']

    return {"errors": []}

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
        value the list of trim settings:
            {"trim": [left trim, mid trim, right trim]}

    POST response:
        If no errors, returns the same as for the GET request.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    gc.collect()
    if request.method == "GET":
        return request.app.hexapod.trim

    # Must be a POST, body could be a list or dict
    trim_list = request.json
    # If it's a dict, we expect the 'trim' key, from which we will the ntake
    # the value which is expected to the trim list.
    if isinstance(trim_list, dict):
        if not "trim" in trim_list:
            return {"errors": ["No 'trim' key in parameters."]}
        trim_list = trim_list['trim']

    if not isinstance(trim_list, list) or len(trim_list) != 3:
        return {"errors": ["Expect a list of three trim values."]}

    request.app.hexapod.trim = trim_list

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
    gc.collect()
    resp = {"errors": []}
    try:
        with_trim = request.json.get("with_trim", True) if request.json else True
        request.app.hexapod.centerServos(with_trim)
    except Exception as exc:
        resp["errors"] = [f"Application error: {exc}"]

    return resp

@app.route('/mem')
async def memInfo(_):
    """
    Returns the current memory status.

    GET:
        Returns:
            {"alloc": int, "free": int}
    """
    gc.collect()
    return {"alloc": gc.mem_alloc(), "free": gc.mem_free()}

#### REVIEW and DELETE ###########
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
        "stroke" (int),     # Amplitude for the leg servos
    }
    """
    gc.collect()
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

        if key == "stroke":
            request.app.hexapod.stroke = val
            continue

        errs.append(f"Invalid param to set: {key}")

    return {"errors": errs}

@app.route('/save_params')
async def saveParams(request):
    """
    Saves the current hexapod config parameters to persistent storage.

    GET Response:
        Same as for getParams call.
    """
    gc.collect()
    return request.app.hexapod.saveParams()

@app.route('/steer', methods=["POST"])
async def steer(request):
    """
    Endpoint to steer the hexapod.

    Both arguments are optional, but if neither is supplied, or both are None,
    and error will be returned.

    POST JSON data:
    {
        "direct": Optional, one of 'fwd', 'rev', 'left' or 'right'
        "angle": Optional, an integer from -180 to 180
    }
    """
    gc.collect()
    dat = request.json
    logging.info("Steering params: %s", dat)

    return request.app.hexapod.steer(dat.get('direct'), dat.get('angle'))

