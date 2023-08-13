"""
Controllers that communicate of the web socket established from the browser.
"""
import uasyncio
import ulogging as logging

# Websocket actions
# * version:[maj.min.patch]
#     >HP: responds by sending a `version` action with the current API version
#     >CL: expects a version response with the current API version.
# * active:ping|pong
#     >HP: responds to a ping by sending `pong`
#     >CL: responds to a ping by sending `pong`
# * memory:[alloc:free]
#     >HP: responds by sending the currently allocated and free memory as bytes
#          values
#     >CL: expects a memory response with the allocated and free values as
#          indicated.
# * trim:[left:mid:right:[center]]
#     >HP: sets and saves the servo trim values if the trim values have been
#          passed in. The center field is optional and if supplied should be
#          'true' or 'false', defaulting to false if not supplied. If true, the
#          servos will be centered after setting the trim values.
#          Always responds with the current trim values.
#     >CL: expects a response as indicated with current trim value - sans the
#          center field. If there was an error setting the values, the args
#          string will be "err:error message"
# * motion:run|pause
#     >HP: run or pause the oscillators
#     >CL: indicator that run or pause was execute
# * speed:int
#     >HP: set the speed to the integer percentage argument between 0% and 100%
#     >CL: indicator that current speed has been set to this percentage value
# * steer:[-]int
#     >HP: set the steering angle to the integer angle between -90° and 90°,
#          with 0° being straight ahead
#     >CL: indicator that steering angle has been set to this angle
# * stroke:int
#     >HP: set the stroke to the integer percentage argument between 0% and 100%
#     >CL: indicator that current stroke has been set to this percentage value
# * fwd
#     >HP: set the direction to forward. Will automatically reset steer angle
#          to 0% and send a `steer` action with newly set 0° angle arg
#     >CL: indicator that forward direction have been set
# * rev
#     >HP: set the direction to reverse. Will automatically reset steer angle
#          to 0% and send a `steer` action with newly set 0° angle arg
#     >CL: indicator that reverse direction have been set
# * rotr
#     >HP: starts rotating right (clockwise). Will automatically reset steer
#          angle to 0% and send a `steer` action with newly set 0° angle arg
#     >CL: indicator that rotate right was started
# * rotr
#     >HP: starts rotating left (anti-clockwise). Will automatically reset steer
#          angle to 0% and send a `steer` action with newly set 0° angle arg
#     >CL: indicator that rotate left was started
# * obst:float|clear
#     >HP: ignored
#     >CL: indicator that an obstacle was detected and the distance in mm as a
#          float, or that a previous obstacle has now been clearer with an
#          argument of 'clear'


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
