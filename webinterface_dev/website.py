#!/usr/bin/env python3
"""
Development server for device web interface.
"""
import socket
import random
import datetime

from bottle import (
    route, get, post, run, request, static_file
)

from config import conf


# Simulate: from version import VERSION
VERSION = '1.2.3'


class Sim:
    """
    Simulates the various hexapod calls available
    """

    def __init__(self):
        """
        Class init.
        """
        self.params = {
            "servo": {
                "mid": {
                    "amplitude": conf['servo']['mid']['amplitude'],
                    "phase_shift": conf['servo']['mid']['phase_shift'],
                    "trim": conf['servo']['mid']['trim'],
                },
                "left": {
                    "amplitude": conf['servo']['left']['amplitude'],
                    "phase_shift": conf['servo']['left']['phase_shift'],
                    "trim": conf['servo']['left']['trim'],
                },
                "right": {
                    "amplitude": conf['servo']['right']['amplitude'],
                    "phase_shift": conf['servo']['right']['phase_shift'],
                    "trim": conf['servo']['right']['trim'],
                }
            },
            "paused": True,
            "period": conf['period'],
        }

    @property
    def speed(self):
        """
        """

    @property
    def speed(self):
        """
        Speed property getter.

        Returns the current speed as a percentage of current period between the
        min and max allowed period.

        Returns:
            The speed percentage as a float
        """
        return round(
            mapTo(self._period, self.PERIOD_MIN, self.PERIOD_MAX, 100, 0),
            2
        )

    @speed.setter
    def speed(self, speed):
        """
        Speed property setter.

        Sets the speed of movement by setting the servo oscillation period.

        The longer the period, the longer it takes to complete one oscillation,
        thus the slower the hexapod moves. The converse is true for a shorter
        period.

        Args:
            speed (int/float): This is a percentage value from 0 to 100%. The period
                will be calculates as this percentage between PERIOD_MIN and
                PERIOD_MAX

        Raises:
            ValueError if the speed value is invalid.
        """
        if not 0 <= speed <= 100:
            raise ValueError(f"Invalid speed percentage: {speed}. 0 - 100")

        period = int(
            round(
                mapTo(speed, 0, 100, self.PERIOD_MAX, self.PERIOD_MIN),
                0
            )
        )
        self.setPeriod(period)

    def _getNetconf(self):
        """
        Returns the local IP as best it can
        """
        #pylint: disable=no-self-use
        dat = {
            'hostname': socket.gethostname(),
        }
        dat['ip'] = socket.gethostbyname(dat['hostname'])

        return dat

    def _valveState(self):
        """
        Simulates getting the current valve status
        """
        #pylint: disable=no-self-use
        return random.choice(['Open', 'Closed', 'Unknown', 'Running'])

    def status(self):
        """
        Returns the status structure
        """
        state = self._getNetconf()
        state['valve_state'] = self._valveState()
        state['app_version'] = VERSION

        return state

#######
# Web routes
#######
@route('/static/<filepath:path>')
def staticFiles(filepath):
    """
    Serves all static files.
    """
    return static_file(filepath, root='./static')

@route('/')
def index():
    """
    Main entry point
    """
    return static_file('index.html', root='./static')

@route('/status')
def vStatus():
    """
    Main entry point
    """
    return sim.status()

@route('/close_valve')
def vClose():
    """
    Called to close the valve.
    """
    print("Closing valve....")

@route('/set_params', method='POST')
def setParams():
    """
    Called to set hexapod runtime parameters
    """
    # Get the json data
    dat = request.json
    errs = []
    # Cycle though the post data an update the parameters
    for key, val in dat.items():
        if key == "speed":
            print(f"Updating speed to {val}%")
        else:
            print(f"Unhandled parameter: {key}")

    res = {
        'success': True,
        'errors': None,
    }

    return res

@route('/home_valve')
def vHome():
    """
    Called to home the valve.
    """
    print("Homing valve....")

@get('/conf')
@post('/conf')
def vConfig():
    """
    Config fetching and updating endpoint.

    For a GET, we return the current config, for a POST, we expect to
    receive the new config values, so we update the config and save
    persistently.
    """
    global conf

    # For a GET we simply return the config as is.
    if request.method == 'GET':
        return conf

    # If not a POST, we moan
    if request.method != 'POST':
        raise ValueError("Only GET or POST allowed")

    # We'll just assume we have the config data
    dat = request.json
    # Simulate booting
    boot = False
    errs = []
    # Cycle though the post data an update the config
    for key in dat:
        if not key in conf:
            errs.append((key, "Invalid config key"))
            continue
        # Set the new value, converting the received string value to the same
        # type currently used in the config.
        try:
            conf[key][1] = type(conf[key][1])(dat[key])
            # Check if a reboot will happen
            boot = key.startswith('mqtt.')
        except Exception as exc:
            errs.append((key, "Error setting value %s: %s" % (dat[key], exc)))

    res = {
        'success': not errs,
        'errors': errs,
        'reboot': boot,
    }

    return res

@get('/update_log')
def otaUpdateLog():
    """
    If an update log file is available, redirect to a download link for it. If
    not return a JSON error payload
    """
    if random.choice([True, False]):
        return {"error": "No OTA update log file available."}

    return static_file(ota_update_log, root='./', mimetype="text/plain")

@get('/update_fw')
def scheduleOTAUpdate():
    """
    Schedule an OTA update by writing the firmware update flag file to the
    filesystem, and scheduling a reboot for the update to be attempted.

    Returns:
        The following structure as application/json content-type:

        {
            'success': bool,   # Indicates if schedule was set up
            'err': str(exc)    # Only if success==False. Error message
        }
    """
    # We simulate a 20% failure
    if random.randint(1, 10) <= 2:
        return {'success': False, 'err': 'The dice are cursed!'}

    # Write some things to the update log to simulate a completed update
    start = datetime.datetime.now()
    pop = range(random.randint(10, 20))
    sample = sorted(random.sample(pop, len(pop)//2))

    with open(ota_update_log, 'w') as f:
        f.write("--- Simulated update ---\n")
        for n in sample:
            log_t = (start + datetime.timedelta(seconds=n)).strftime("%Y-%m-%d %H:%M:%S")
            what = random.choice(
                ('happened', 'changed', 'was updated', 'was deleted', 'went wrong')
            )
            f.write(f"{log_t} : Something {what} here.\n")

    return {'success': True}

sim = Sim()

run(host='0.0.0.0', port=5000, reloader=True, debug=True)
