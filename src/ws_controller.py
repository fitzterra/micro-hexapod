"""
Controllers that communicate of the web socket established from the browser.
"""

import uasyncio
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
        await wsock.send('{"ping": 1}')

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
