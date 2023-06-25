"""
Main runtime
"""
import gc
import uasyncio
from lib.wemosD1_maps import LED as led_pin
from led import LED
from hexapod import Hexapod
from config import conf


async def connect():
    """
    Connects to the network
    """
    from lib.networking import connectToAP
    led = LED(-led_pin)
    led.flash()
    res = await connectToAP()
    if res:
        led.noFlash(True)
    gc.collect()

if __name__ == "__main__":
    loop = uasyncio.get_event_loop()

    hexapod = Hexapod(conf['pins'])

    # Try to connect to the access point
    loop.create_task(connect())
    if conf['web_app']['enabled']:
        from hexapod_api import runserver, app as webapp
        webapp.hexapod = hexapod
        loop.create_task(runserver())

    loop.create_task(hexapod.run())

    loop.run_forever()
