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
import os
import sys
# Make sure we can import anything from lib without specifically indicating
# this. MicroPython running on the device does the same thing
sys.path.insert(0, 'lib')

#pylint: disable=wrong-import-position
import uasyncio
import ulogging as logging
from lib import hcsr04
from config import conf

# Before importing the API stuff, we need to let the webserver know that the
# static files in this environment is not gzipped.
import webserver
webserver.GZIPPED_STATIC = False

class HCSR04Sim:
    """
    Simulator for the HCSR04 Ultrasonic Distance Sensor.
    """
    AVG_INPUT = 'dist_values.txt'

    def __init__(self, trig, echo, max_range=4000):
        """
        Instance constructor.

        Args:
            trig (int): Trigger pin - ignored
            echo (int): Echo pin - ignored
            max_range (int) : Maximum distance to measure for in mm
        """
        #pylint: disable=unused-argument
        self._max_range = max_range
        self._buf = []
        self._avg = None

    async def monitor(self, sample_delay=500, window=10):
        """
        Simulates taking measurement samples.

        To control the simulation from external, this task will monitor the
        file system for an input file (named by AVG_INPUT) with some sample
        distance measures. If found, it will open the file and read distance
        measure value from this file one line at a time, with a sample_delay
        delay between each reading.
        Each reading will then be pushed into the window, and the average
        calculated.
        Once all lines have been read, the file will be closed and then
        deleted. This will be a sign for the external process to know that all
        samples have been read.

        Any invalid lines in the file will be ignored.
        """
        in_file = None
        logging.info("Setting up HCSR04 monitor task.")

        while True:
            # We drain the window by one on every iteration.
            if self._buf:
                self._buf.pop(0)

            # Do we need to look for the input file?
            if in_file is None:
                # NOTE
                # Something very weird happening here.
                # When trying to open the file and checking if it exists by
                # catching the OSError, it seems that this exception is somehow
                # bubbling up to other asyncio coros, and causing these to
                # exit.
                # Specifically, if a web requests is made after this error was
                # raised below, even if it is handled as is done here, the
                # microdot writer to write the response will exit with this
                # error `OSError: [Errno 9] EBADF` which is def not related to
                # the socket. I have a feeling this is a bug in Micropython, so
                # to get around this, we call os.listdir to see if the input
                # file is available.
                ##- try:
                ##-     in_file = open(self.AVG_INPUT, 'r')
                ##- except OSError as exc:
                ##-     # Assume the file does not exist
                ##-     in_file = None

                # Workaround to above to see if input file is available, and
                # open if if it is.
                if self.AVG_INPUT in os.listdir():
                    in_file = open(self.AVG_INPUT)

            # Do we have an open input file?
            if in_file is not None:
                # Read until a valid line is read, or we reach the end of the
                # file, or we've filled the window
                # Read lines from the file until we've filled the buffer with
                # valid entries (invalid entries are ignored), or we get the
                # end of the file.
                while len(self._buf) < window:
                    # This will return only an empty string without a newline
                    # when at end of file.
                    line = in_file.readline()

                    # End of file?
                    if line == '':
                        # Close the file, reset in_file and exit the while loop
                        in_file.close()
                        in_file = None
                        # Try to delete the file
                        try:
                            os.unlink(self.AVG_INPUT)
                        except Exception:
                            logging.error("Error deleting file: [%s]", self.AVG_INPUT)
                        break
                    # Remove the newline
                    line = line.strip()
                    # Valid?
                    if line.isdigit():
                        logging.info("Adding to measurements: %s", line)
                        self._buf.append(float(line))
                    else:
                        logging.error("Ignoring invalid measurement: [%s]", line)

            # Update the average if we can
            self._avg = None if not self._buf else round(sum(self._buf)/len(self._buf), 2)

            # Delay
            await uasyncio.sleep_ms(sample_delay)

    def avg(self):
        """
        Simulates returning the average measurement of an obstacle in front of
        the sensor.

        The average is calculated by the monitor coro.
        """
        return self._avg

# Monkey patch the hcsr04 module, replacing the HCSR04 class with out simulator
# before we import the Hexapod class below
hcsr04.HCSR04 = HCSR04Sim

#pylint: disable=wrong-import-position
import hexapod as hexapod_mod
from hexapod_api import runserver, app as webapp


def _handleException(_, context):
    """
    Global uasyncio exception handler.
    """
    # This is in micropython sys module @pylint: disable=no-member
    print("Shit just happened....")
    if isinstance(context['exception'], TypeError):
        print("Looks like the browser reloaded. Gonna ignore this:")
        sys.print_exception(context['exception'])
        return
    # Some other error
    sys.print_exception(context['exception'])
    sys.exit()

# Adjust the distance simulator default delay to a slightly higher value while
# we are simulating.
hexapod_mod.OBS_SAMPLE_DELAY = 800

loop = uasyncio.get_event_loop()
loop.set_exception_handler(_handleException)
logging.info("Setting up Hexapod.")
hexapod = hexapod_mod.Hexapod(conf['pins'], conf['echo_sense'])

webapp.hexapod = hexapod
loop.create_task(runserver(port=5000))

loop.create_task(hexapod.run())

loop.run_forever()
