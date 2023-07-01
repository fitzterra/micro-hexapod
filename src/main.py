"""
Main runtime
"""
import gc
import uasyncio
import ulogging as logging
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


if __name__ == "__main__":
    netCon()
    gc.collect()
    logging.info("Setting up Hexapod.")
    logging.info("Mem free: %s", gc.mem_free())

    loop = uasyncio.get_event_loop()

    hexapod = Hexapod(conf['pins'])

    # Try to connect to the access point
    # loop.create_task(connect())

    if conf['web_app']['enabled']:
        from hexapod_api import runserver, app as webapp
        webapp.hexapod = hexapod
        loop.create_task(runserver())

    loop.create_task(hexapod.run())

    loop.run_forever()
