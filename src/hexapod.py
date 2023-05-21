"""
Main hexapod controller module
"""

import uasyncio
from servo import ServoOscillator
from config import conf, getByDotKey
from map_to import mapTo

class Hexapod:
    """
    Hexapod controller
    """

    PERIOD_MAX = 3000
    PERIOD_MIN = 500

    def __init__(self):
        """
        Hexapod instance initializer.

        """
        self._paused = False
        self._period = conf['period']
        self.servos = {}
        # Create the left, mid and right servos, configuring it from the config
        # options
        for servo in ['left', 'mid', 'right']:
            self.servos[servo] = ServoOscillator(
                pin=getByDotKey(f'servo.{servo}.pin'),
                trim=getByDotKey(f'servo.{servo}.trim'),
                amplitude=getByDotKey(f'servo.{servo}.amplitude'),
                phase_shift=getByDotKey(f'servo.{servo}.phase_shift'),
                period=self._period,
            )
        self.pause = True

    @property
    def pause(self):
        """
        Paused state getter.

        Returns:
            True if currently paused, False otherwise
        """
        return self._paused

    @pause.setter
    def pause(self, paused):
        """
        Pause setter.

        Args:
            paused (bool): True to pause all legs, False to unpause
        """
        self._paused = paused
        # Now set the servo oscillator pase attribute for each leg
        for servo in self.servos.values():
            servo.pause = self._paused

    def setPeriod(self, period):
        """
        Sets the period for all servos to the period supplied.

        Args:
            period (int): The oscillation period to set. This must be value
                between PERIOD_MIN and PERIOD_MAX inclusive.

        Returns:
            None on success
            An error string on error.
        """
        if not self.PERIOD_MIN <= period <= self.PERIOD_MAX:
            return f"Invalid period: {period}. {self.PERIOD_MIN} - {self.PERIOD_MAX}"

        self._period = period
        for servo in self.servos.values():
            servo.period = period

        return None

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
            'servo': {}
        }
        for servo_name, servo_inst in self.servos.items():
            params['servo'][servo_name] = {}
            for param in ['trim', 'amplitude', 'phase_shift']:
                params['servo'][servo_name][param] = getattr(servo_inst, param)

        return params

    def centerServos(self):
        """
        Sets all servos to their center positions at 90°
        """

        for servo in self.servos.values():
            servo._servo.angle = 90

        return {"errors": []}


    async def run(self):
        """
        Runs the hexapod by creating update asyncio tasks for each of the
        servos.

        These servos will be updates as long as the uasyncio loop is running,
        so this should be managed external to this call.

        After calling this method, any of the other config or set methods can
        be called to change hexapod behaviour in order to control
        it???????????????
        """
        for servo in self.servos.values():
            uasyncio.create_task(servo.update())

