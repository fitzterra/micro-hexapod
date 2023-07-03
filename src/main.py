"""
Main runtime
"""
import gc
import sys
import uasyncio
import ulogging as logging
from led import LED
from wemosD1_maps import LED as LED_PIN
from hexapod import Hexapod
from config import conf

def netCon():
    """
    """
    from wifi_manager import connSetup

    # Connect to WiFi. This will only return if the connection was successful.
    # If not, it will setup up a local AP (see AP_ESSID and AP_PASSWD in
    # wifi_manager) for the user to connect to, and then start a web config on
    # http://192.168.4.1 to configure the AP.
    logging.info("Connecting to default WiFi AP....")
    connSetup(reset=True)  # Normally a good idea to pass reset=True for ESP8266

    # Try to get some memory back
    logging.info("Mem free before: %s", gc.mem_free())
    del connSetup
    gc.collect()
    logging.info("Mem free after: %s", gc.mem_free())

def _handleException(loop, context):
    """
    Global uasyncio exception handler.
    """
    logging.error("Exception: %s", context)


if __name__ == "__main__":
    # Turn the onboard LED on full on startup. If we go into AP mode, it will
    # stay on as indicator.
    # NOTE on the Wemos D1 the LED is connected to the high side, so we pass it
    #   as a negative pin number to invert the on/off state.
    led = LED(-LED_PIN)
    led.on()

    netCon()
    gc.collect()
    logging.info("Setting up Hexapod.")
    logging.info("Mem free: %s", gc.mem_free())

    loop = uasyncio.get_event_loop()
    loop.set_exception_handler(_handleException)

    # Now we have connected to the local network, and will be running an
    # asyncio event loop, so we can switch the LED to flashing mode to
    # indicate we are connected and ready.
    led.flash()

    hexapod = Hexapod(conf['pins'])

    # Try to connect to the access point
    # loop.create_task(connect())

    if conf['web_app']['enabled']:
        from hexapod_api import runserver, app as webapp
        webapp.hexapod = hexapod
        loop.create_task(runserver())

    loop.create_task(hexapod.run())

    loop.run_forever()
