"""
Controllers that communicate of the web socket established from the browser.
"""

import uasyncio
import ulogging as logging

# Websocket actions
# * ping
#     >HP: responds by sending `pong`
#     >CL: responds by sending `pong`
# * pong
#     >HP: no action
#     >CL: no action
# * run
#     >HP: run the oscillators
#     >CL: indicator that run state was entered
# * stop
#     >HP: stop the oscillators
#     >CL: indicator that stop state was entered
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
# * obst:[float|clear]
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
        await wsock.send('ping')

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

    while True:
        dist = hexapod.obstacle
        # Not configured?
        if dist == -1:
            logging.error("Obstacle monitor not setup up. Exiting monitor.")
            break
        # Obstacle?
        if dist is not None:
            # Send obstacle info
            await wsock.send('{"obs": %f}' % dist)

        await uasyncio.sleep_ms(interval)
