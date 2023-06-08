"""
Hexapod controller.
"""
import uasyncio
import ulogging as logging
from servo import ServoOscillator
from config import conf, getByDotKey, persist
from map_to import mapTo

# Indexes into 3 element arrays representing the three servos. These will
# always be in the order LEFT, MID, RIGHT
LEFT, MID, RIGHT = (0, 1, 2)

# Default phases for Left, Mid and Right servos for different movements
FWD = [0, 90, 0]     # Walk forward
REV = [90, 0, 90]    # Walk backwards
RGT = [0, 90, 180]   # Turn to the right on the spot in a forward direction
LFT = [180, 90, 0]   # Turn to the left on the spot in a forward direction

def clamp(val, vmin, vmax):
    """
    Clamps an value between a min and max value.

    Args:
        val (number): Value to clamp
        vmin (number): The min value to clamp to
        vmixn (number): The max value to clamp to

    Returns:
        val if it falls between (inclusive) vmin and vmax, else vmin if val is
        less than vmin, or vmax if it's greater than vmax.
    """
    # This is (at least in 2013) faster than using min(vmax, max(vmin, val))
    # See: https://stackoverflow.com/a/18610587
    return vmin if val < vmin else vmax if val > vmax else val

class Hexapod:
    """
    Controller for the hexapod.
    """
    # Min an max oscillation period (time to complete on oscillation) in
    # milliseconds
    PERIOD_MAX = 3000   # Slow
    PERIOD_MIN = 500    # Fast
    # This is min and max degrees the left and right servos may move per
    # oscillation cycle. It translates to the amplitude value for the left and
    # right servos.
    # The min and max in theory is 0° - 90°, but the legs may be restricted due
    # to the design and not allow a full 90° movement.
    STROKE_MIN = 0
    STROKE_MAX = 90

    # Used to prefix all log messages so we can see what logs which message
    LOG_PREFIX = "Hexapod"

    def __init__(self, pins, setup=None):
        """
        Instance initialiser.

        Args:
            pins (list): a list of IO pins the left, mid and right (in that
                order) servos are connected to.
            setup (dict): Optional setup config dictionary to override any
                default setup values. Format:
                {
                    'period': the oscillation period in milliseconds between
                        PERIOD_MAX and PERIOD_MIN,
                    'phase': a 3 element list for phase shift values for each servo
                    'trim': a 3 element list for trim values for each servo,
                    'mid_ampl': the oscillation amplitude for the mid leg. This
                        determines how high the other legs are lifted of the
                        ground.
                    'stroke': the amplitude for the left and right legs. This
                        determines how far the lefts are move forwards and
                        backwards, and must be in the STROKE_MIN and STROKE_MAX
                        range.
                }
        """
        # Make sure setup is a dict is not supplied
        if not setup:
            setup = {}

        self._pins = pins
        self._period = clamp(setup.get('period', 2000), self.PERIOD_MIN, self.PERIOD_MAX)
        self._phase = setup.get('phase', FWD)
        self._trim = setup.get('trim', [0, 0, 0])
        self._mid_ampl = setup.get('mid_ampl', 10)
        self._stroke = clamp(setup.get('stroke', 30), self.STROKE_MIN, self.STROKE_MAX)
        self._servos = []  # Will be set to Oscillator instances by _setOscillators
        self._paused = True
        # Create the oscillators
        self._setOscillators()

    def _setOscillators(self):
        """
        Sets up all three servo oscillators.
        """
        for servo in (LEFT, MID, RIGHT):
            logging.info("%s: Setting up oscillator: %s", self.LOG_PREFIX, servo)
            self._servos.append(
                ServoOscillator(
                    pin=self._pins[servo],
                    trim=self._trim[servo],
                    amplitude=self._mid_ampl if servo == MID else self._stroke,
                    phase_shift=self._phase[servo],
                    period=self._period,
                )
            )
            self._servos[-1].pause = self._paused

    @property
    def params(self):
        """
        Property to return the current servo properties.

        Returns:
            {
                'paused': boolean
                'pins': [left, mid, right],
                'period': int,
                'phase': [left, mid, right],
                'trim': [left, mid, right],
                'mid_ampl': int,
                'stroke': int,
                'legs_ampl': [left, right],
            }
        """
        params = {}
        for param in [
                '_paused',
                '_pins',
                '_period',
                '_phase',
                '_trim',
                '_mid_ampl',
                '_stroke']:
            params[param[1:]] = getattr(self, param)
        # Need to fetch the left and right amplitudes off the servos
        params['legs_ampl'] = [self._servos[s].amplitude for s in (LEFT, RIGHT)]
        logging.info("%s: Returning params: %s", self.LOG_PREFIX, params)

        return params

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
            paused (bool): True to pause all oscillators, False to unpause
        """
        logging.info("%s: Setting pause to: %s", self.LOG_PREFIX, paused)
        self._paused = paused
        # Now set the servo oscillator pause attribute for each leg
        for servo in self._servos:
            servo.pause = self._paused

    @property
    def trim(self):
        """
        Returns the trim for each of the servos.

        Returns:
            [left trim, mid trim, right trim]
        """
        return self._trim

    @trim.setter
    def trim(self, trim):
        """
        Sets the trim for one or more of the servos.

        The trim degrees for each servo is given in 3 element list. Any element
        that is None will not change that servo's trim.

        For e.g. to only set the mid servo trim, pass the trim list as :
            [None, 10, None]

        Args:
            trim (list): [left trim, mid trim, right trim]
        """
        logging.info("%s: Setting servos trim: %s", self.LOG_PREFIX, trim)
        # Run over each servo, setting both the self._trim element for the
        # servos, as well as the actual servo trim
        for idx, servo in enumerate(self._servos):
            logging.info(
                "%s: Setting servo %s trim to: %s",
                self.LOG_PREFIX,
                idx,
                "Not changing" if trim[idx] is None else trim[idx]
            )
            if trim[idx] is None:
                continue
            # Set the servo trim and our trim value
            servo.trim = trim[idx]
            self._trim[idx] = trim[idx]

    def centerServos(self, with_trim=True):
        """
        Centers all servos with or without the current trim adjustment for the
        servo

        This call will also force the hexapod to it's pause state.
        """
        logging.info(
            "%s: Centering servos %s trim",
            self.LOG_PREFIX,
            "with" if with_trim else "without"
        )
        # The center_servo call will auto pause each servo, but we sill have to
        # sync the global pause state. Do not call the pause setter as this
        # will cycle through each servo and force a pause, while the
        # center_servo() call will automatically do the pause for each servo.
        self._paused = True
        # Center all.
        for servo in self._servos:
            servo.center_servo(with_trim)

    async def run(self):
        """
        Runs the hexapod by creating update asyncio tasks for each of the
        servos.

        These servos will be updated as long as the uasyncio loop is running,
        so this should be managed external to this call.

        After calling this method, and if an asyncio loop is being run, any of
        the other config or set methods can be called to change hexapod
        behaviour in order to control it.
        """
        logging.info("%s: creating update tasks for oscillators", self.LOG_PREFIX)
        for servo in self._servos:
            uasyncio.create_task(servo.update())
