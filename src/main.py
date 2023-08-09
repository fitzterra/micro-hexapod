"""
Main runtime
"""
import sys
import gc
import uasyncio
import ulogging as logging
from lib.led import LED
from hexapod import Hexapod
from config import conf

def netCon():
    """
    Manages the network connecting on startup.
    """
    from lib.wifi_manager import connSetup

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

def _handleException(_, context):
    """
    Global uasyncio exception handler.
    """
    err_msg = context.get("exception", context['message'])
    logging.error("Exception: %s", err_msg)
    # We also print detailed exception info. It does not look like it is easy
    # to get this exception info into a string to add to the logging, so we do
    # the next best thing.
    sys.print_exception(context['exception']) #pylint: disable=no-member


if __name__ == "__main__":
    # Turn the onboard LED on full on startup. If we go into AP mode, it will
    # stay on as indicator.
    led = LED(conf['led_pin'])
    led.on()

    netCon()
    gc.collect()
    logging.info("Mem free: %s", gc.mem_free())

    loop = uasyncio.get_event_loop()
    loop.set_exception_handler(_handleException)

    # Now we have connected to the local network, and will be running an
    # asyncio event loop, so we can switch the LED to flashing mode to
    # indicate we are connected and ready.
    led.flash()

    # Create the hexapod instance.
    logging.info("Setting up Hexapod.")
    hexapod = Hexapod(conf['pins'], conf['echo_sense'])

    if conf['web_app']['enabled']:
        from hexapod_api import runserver, app as webapp
        webapp.hexapod = hexapod
        loop.create_task(runserver())

    loop.create_task(hexapod.run())

    loop.run_forever()
