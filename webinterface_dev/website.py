#!/usr/bin/env python3
"""
Development server for device web interface.
"""

from bottle import (
    route, get, post, run, request, static_file
)

from map_to import mapTo


# Simulate: from version import VERSION
VERSION = '1.2.3'


class Sim:
    """
    Simulates the various hexapod calls available
    """

    PERIOD_MAX = 3000
    PERIOD_MIN = 500

    def __init__(self):
        """
        Class init.
        """
        self._period = 2000
        self._paused = True
        self.servos = {
            "left": {
                "amplitude": 30,
                "phase_shift": 0,
                "trim": 0,
            },
            "mid": {
                "amplitude": 10,
                "phase_shift": 90,
                "trim": 0,
            },
            "right": {
                "amplitude": 30,
                "phase_shift": 0,
                "trim": 0,
            },
        }

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
        self._period = period

    def getParams(self):
        """
        Returns all runtime parameters and their current values.

        Returns:
            The current params as a dictionary:
            {
                "servo": {
                    "mid": {
                        "amplitude": (int),
                        "phase_shift": (int),
                        "trim": (int)
                    },
                    "left": {
                        "amplitude": (int),
                        "phase_shift": (int),
                        "trim": (int)
                    },
                    "right": {
                        "amplitude": (int),
                        "phase_shift": (int),
                        "trim": (int)
                    }
                },
                "paused": (bool),
                "period": (int),
                "speed": (float),   # Period as a % of min and max periods
            }
        """
        params = {
            'period': self._period,
            'speed': self.speed,
            'paused': self._paused,
            'servo': self.servos
        }

        return params

    def centerServos(self):
        """
        Enters the pause state for all servos and then sets them to their
        center position (90°) taking the trim for each servo into account.
        """
        # The ServoOscillator has a center_servo() method that will auto pause
        # the servos, but here we only have to set the global pause
        self._paused = True

        return self.getParams()

    def saveParams(self):
        """
        simulates saving the current parameters to persistent storage.
        """
        return self.getParams()

    def steer(self, direct=None, angle=None):
        """
        Simulates the steer call.
        """
        print(f"Steering: direct={direct}, angle={angle}")

        return {
            'success': True,
            'errors': None,
        }


sim = Sim()

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

@route('/get_params')
def getParams():
    """
    Returns the current hexapod parameters.
    """
    return sim.getParams()

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
            sim.speed = val
            continue

        # We do not set both speed and period if both are present. We favor
        # speed and do not set period if speed is provided. To set period, do
        # not not also provide the speed.
        if key == "period":
            if "speed" in dat:
                print("Ignoring period update since speed is also provided.")
            else:
                print(f"Updating period to {val}")
                sim._period = val
            continue

        if key == "paused":
            print(f"Updating paused to {val}")
            sim._paused = val
            continue

        if key == "servo":
            for servo, params in val.items():
                if not servo in sim.servos:
                    errs.append(f"No servo named: {servo}")
                    continue
                for pkey, pval in params.items():
                    if not pkey in ['amplitude', 'phase_shift', 'trim']:
                        errs.append(f"Invalid param for servo {servo}: {pkey}")
                        continue
                    print(f"Updating servos['{servo}']['{pkey}'] to {pval}")
                    sim.servos[servo][pkey] = pval
            continue


        err = f"Unhandled parameter: {key}"
        print(err)
        errs.append(err)

    res = {
        'success': True,
        'errors': None,
    }

    return res

@route('/center_servos', method='GET')
def centerServos():
    """
    Called to center all servos.
    """
    return sim.centerServos()

@route('/save_params', method='GET')
def saveParams():
    """
    Called to save the current parameters to persistent storage.
    Returns the params that have been saved.
    """
    return sim.saveParams()

@route('/steer', method='POST')
def steer():
    """
    Called to steer the hexapod
    """
    dat = request.json
    return sim.steer(direct=dat.get('direct'), angle=dat.get('angle'))


run(host='0.0.0.0', port=5000, reloader=True, debug=True)
