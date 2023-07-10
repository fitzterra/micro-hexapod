#!/usr/bin/env micropython
"""
Simulates the Hexapod for local rapid development.

This starts up a simulated Hexapod web and API server.
It requires that the micropython unix port executable is in the path.
It uses the very minimal `machine` simulation for running under the unix port,
and then initialises the hexapod and API in a very similar way that the main
function will do when running on the MCU.

This is handy for rapid development of the web and API components.
"""
import uasyncio
import ulogging as logging
from hexapod import Hexapod
from config import conf

# Before importing the API stuff, we need to let the webserver know that the
# static files in this environment is not gzipped.
import webserver
webserver.GZIPPED_STATIC = False

#pylint: disable=wrong-import-position
from hexapod_api import runserver, app as webapp

loop = uasyncio.get_event_loop()
logging.info("Setting up Hexapod.")
hexapod = Hexapod(conf['pins'])

webapp.hexapod = hexapod
loop.create_task(runserver(port=5000))

loop.create_task(hexapod.run())

loop.run_forever()
