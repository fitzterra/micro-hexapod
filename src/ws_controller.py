"""
Controllers that communicate via the web socket established from the browser.
"""
import uasyncio
from webserver import gc, app, logging
from microdot_asyncio_websocket import with_websocket
from version import VERSION
import ulogging as logging

PING_DELAY = 5 # seconds

async def ping(wsock):
    """
    Task to send regular pings to the remote end of the web socket.

    Args:
        wsock (socket): The web socket once the connection was been made.
    """

    while True:
        await uasyncio.sleep(PING_DELAY)
        logging.info("Sending ping...")
        await wsock.send('active:ping')

async def obstacleReporter(hexapod, wsock, interval=1000):
    """
    Task to query the hexapod for any obstacles and if any, report it on the
    websocket.

    If the hexapod does not have a distance sensor configured (obstacle
    property returns -1), this task will exit.

    Args:
        hexapod (inst): Hexapod instance.
        wsock (socket): The open websocket instance
        interval (int): Interval between obstacle checks in milliseconds
    """
    dist = hexapod.obstacle
    # Not configured?
    if dist == -1:
        logging.error("Obstacle monitor not setup up. Exiting monitor.")
        return

    has_cleared = True
    while True:
        dist = hexapod.obstacle
        # Obstacle?
        if dist is not None:
            # Send obstacle info
            await wsock.send(f'obst:{dist}')
            # Indicate that we have send a cleared message once the obstacle is
            # cleared later.
            has_cleared = False
        elif not has_cleared:
            # No obstacle detected, but we have also not let the client know
            # that it is now cleared. Do it now
            await wsock.send('obst:clear')
            # We only want to send the cleared message once, so set the cleared
            # flag
            has_cleared = True

        await uasyncio.sleep_ms(interval)

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

    # Need to set trims?
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

def handleMotion(val, hexapod):
    """
    Handles a request to run or pause the oscillators.

    Args:
        val (str): Either "run" or "pause"
        hexapod (inst): Instance of the hexapod

    Returns:
        "run" or "pause" to indicate the current state
    """
    # Validate input
    if val not in ('run', 'pause'):
        logging.info("Invalid motion request: %s", val)
        return f"err:Invalid motion request: {val}"

    # Either pause or do not...
    hexapod.pause = (val == 'pause')

    # We can just return what the requested state is to indicate the new
    # state
    return val

def handleDirection(val, hexapod):
    """
    Handles a request to set a direction.

    Will always reset the steer angle to 0° if it it was not at 0° already.

    Args:
        val (str): One of 'fwd', 'rev', 'rotr' or 'rotl'
        hexapod (inst): Instance of the hexapod

    Returns:
        A dictionary to indicate the current direction and angle:
        {
            'dir': one of 'fwd', 'rev', 'rotr', 'rotl'
            'angle': current angle for the direction
        }
    """
    # Validate input
    if val not in ('fwd', 'rev', 'rotr', 'rotl'):
        logging.info("Invalid direction request: %s", val)
        return f"err:Invalid direction request: {val}"

    # Either pause or do not...
    hexapod.steer = {'dir': val}

    # We just return the current steer result
    return hexapod.steer

def handleAngle(val, hexapod):
    """
    Handles a request to set the steer angle.

    Args:
        val (str): An angle: -90 <= val <= 90
        hexapod (inst): Instance of the hexapod

    Returns:
        The angle as set or and error
    """
    # Validate input
    try:
        # Convert to base 10 integer
        angle = int(val, 10)
        if not -90 <= angle <= 90:
            raise ValueError
    except ValueError:
        logging.info("Invalid angle: %s", val)
        return f"err:Invalid angle: {val}"

    # If the current direction is not valid for setting and angle, a ValueError
    # will be raised
    try:
        hexapod.steer = {'angle': angle}
    except ValueError as exc:
        logging.info("Error setting angle %s", exc)
        return f"err:{exc}"

    # We just return the current angle
    return val

def handleSpeed(val, hexapod):
    """
    Handles a request to set the speed.

    Args:
        val (str): A speed percentage: 0 <= val <= 100
        hexapod (inst): Instance of the hexapod

    Returns:
        The speed percentage as set or and error
    """
    # Validate input
    try:
        # Convert to base 10 integer
        speed = int(val, 10)
        if not 0 <= speed <= 100:
            raise ValueError
    except ValueError:
        logging.info("Invalid speed: %s", val)
        return f"err:Invalid speed: {val}"

    try:
        hexapod.speed = speed
    except ValueError as exc:
        logging.info("Error setting speed %s", exc)
        return f"err:{exc}"

    # We just return the current speed
    return val

def handleStroke(val, hexapod):
    """
    Handles a request to set the stroke percentage.

    Args:
        val (str): A stroke percentage: 0 <= val <= 100
        hexapod (inst): Instance of the hexapod

    Returns:
        The stroke percentage as set or and error
    """
    # Validate input
    try:
        # Convert to base 10 integer
        stroke = int(val, 10)
        if not 0 <= stroke <= 100:
            raise ValueError
    except ValueError:
        logging.info("Invalid stroke: %s", val)
        return f"err:Invalid stroke: {val}"

    try:
        hexapod.stroke = stroke
    except ValueError as exc:
        logging.info("Error setting stroke %s", exc)
        return f"err:{exc}"

    # We just return the current stroke
    return val

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
        elif action == 'memory':
            response = f"memory:{gc.mem_alloc()}:{gc.mem_free()}"
        elif action == 'pong':
            logging.info("Received pong...")
        elif action == 'center':
            logging.info("Received serve center request...")
            # Center, taking trim into account
            hexapod.centerServos(True)
            # This could have affected the state of motion, so we return the
            # current pause state
            response = f"motion:{'pause' if hexapod.pause else 'run'}"
        elif action == 'trim':
            logging.info(f"Received trim:{args}...")
            response = f"trim:{handleTrim(args, hexapod)}"
        elif action == 'motion':
            logging.info(f"Received motion:{args}...")
            response = f"motion:{handleMotion(args, hexapod)}"
        elif action == 'dir':
            logging.info(f"Received dir:{args}...")
            # We will be sending a response for the direction as well as for
            # the steering angle
            resp = handleDirection(args, hexapod)
            # Set up the response tuple
            response = (
                f"dir:{resp['dir']}",
                f"angle:{resp['angle']}",
            )
        elif action == 'angle':
            logging.info(f"Received angle:{args}...")
            response = f"angle:{handleAngle(args, hexapod)}"
        elif action == 'speed':
            logging.info(f"Received speed:{args}...")
            response = f"speed:{handleSpeed(args, hexapod)}"
        elif action == 'stroke':
            logging.info(f"Received stroke:{args}...")
            response = f"stroke:{handleStroke(args, hexapod)}"
        else:
            logging.info(f"Unhandled action: {action}")

        # Any response?
        if response:
            # To handle multiple responses, we force the response into a list
            # if not one already
            if not isinstance(response, (list, tuple)):
                response = (response,)
            for resp in response:
                await ws.send(resp)
