"""
Hexapod controller.
"""
import uasyncio
import ulogging as logging
from lib.servo import ServoOscillator
from lib.hcsr04 import HCSR04

# Indexes into 3 element arrays representing the three servos. These will
# always be in the order LEFT, MID, RIGHT
LEFT, MID, RIGHT = (0, 1, 2)

# Default phases for Left, Mid and Right servos for different movements
FWD = [0, 90, 0]     # Walk forward
REV = [90, 0, 90]    # Walk backwards
ROTR = [0, 90, 180]   # Turn to the right on the spot in a forward direction
ROTL = [180, 90, 0]   # Turn to the left on the spot in a forward direction

# These are defaults for the obstacle sensor
# The number of milliseconds to wait between obstacle detection samples
OBS_SAMPLE_DELAY = 10
# The size of the moving average sample window for averaging obstacle samples
OBS_SAMPLE_WINDOW = 20

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
    #pylint: disable=too-many-instance-attributes

    # Min an max oscillation period (time to complete on oscillation) in
    # milliseconds
    PERIOD_MAX = 3000   # Slow
    PERIOD_MIN = 500    # Fast
    # This is min and max degrees the left and right servos may move per
    # oscillation cycle.
    # The min and max in theory is 0° - 180°, but the legs may be restricted due
    # to the design and not allow a full 90° movement.
    # Test this directly setting servo angles and see how far they can go in
    # either direction without touching the body.
    # NOTE: Best is to keep these symmetrical, i.e. :
    #   STROKE_MAX_ANGL == 180-STROKE_MIN_ANGL
    # or vice versa depending to which side the restriction is greatest.
    STROKE_MIN_ANGL = 35
    STROKE_MAX_ANGL = 145
    # This is the calculated max stroke for the left and right servos based on
    # the max stroke angles. The difference between min and max is the total
    # stroke angle available, but this angle is split around the 90° rotation
    # point, so only half of this will be available as the final amplitude
    # for the left/right servos
    STROKE_MAX = (STROKE_MAX_ANGL - STROKE_MIN_ANGL) // 2

    # Used to prefix all log messages so we can see what logs which message
    LOG_PREFIX = "Hexapod"

    # The file to store trim settings in for persistence.
    TRIM_FILE = 'settings_trim.saved'

    def __init__(self, pins, sense=None, setup=None):
        """
        Instance initialiser.

        Args:
            pins (list): a list of IO pins the left, mid and right (in that
                order) servos are connected to.
            sense (list): An optional config for an HCSR04 Ultrasonic Distance
                sensor. If not None, if should be a list as follows:
                [trigger_pin, echo_pin, max_range]
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
                        determines how far the legs are move forwards and
                        backwards, and must be in the STROKE_MAX range.
                }
        """
        # Make sure setup is a dict if not supplied
        if not setup:
            setup = {}

        self._pins = pins
        self._period = clamp(setup.get('period', 2000), self.PERIOD_MIN, self.PERIOD_MAX)
        self._phase = setup.get('phase', FWD)
        self._trim = setup.get('trim', [0, 0, 0])
        self._mid_ampl = setup.get('mid_ampl', 10)
        self._stroke = clamp(setup.get('stroke', 30), 0, self.STROKE_MAX)
        self._servos = []  # Will be set to Oscillator instances by _setOscillators
        self._paused = True
        self._steer_dir = 'fwd'
        self._steer_angle = 0
        # Read and update any saved trim values
        self._getSavedTrim()
        # Create the oscillators
        self._setOscillators()
        # Will we set by _setupObstacleSensor if an HCSR04 config is supplied
        # in the sense argument
        self._sense = None
        self._setupObstacleSensor(sense)

    def _saveTrim(self):
        """
        Saves the current trim setting to persistent local storage.

        The compliment is the _getTrim() method which would read the trim
        settings from local storage again.

        If there are any error saving the trim values, an error would be
        logged, but no exceptions would be raised.
        """
        try:
            with open(self.TRIM_FILE, 'w') as trim_f:
                # We simply write all three values as a comma separated list
                trim_f.write(','.join([str(v) for v in self._trim]))
                logging.info(
                    "%s: Saved trim values to %s: %s",
                    self.LOG_PREFIX,
                    self.TRIM_FILE,
                    self._trim
                )
        except OSError as exc:
            logging.error("%s: Error saving trim values: %s", self.LOG_PREFIX, exc)

    def _getSavedTrim(self):
        """
        Tries to read the saved trim setting in the local file named by
        self.TRIM_FILE, and if valid trim settings are found, overrides
        self._trim with these values.
        """
        try:
            with open(self.TRIM_FILE, 'r') as trim_f:
                trim = trim_f.read().strip()
                # We expect a comma separated string
                trim_vals = trim.split(',')
                if len(trim_vals) != 3:
                    logging.error(
                        "%s: Invalid saved trim values: %s", self.LOG_PREFIX, trim
                    )
                    return
                # Convert all values to integers
                trim_vals = [int(v) for v in trim_vals]
                # For safety we do not allow trim values greater than 10° in
                # either direction
                if not all(-10 <= v <= 10 for v in trim_vals):
                    logging.error(
                        "%s: Some trim values out of the -10 to 10 range: %s",
                        self.LOG_PREFIX, trim_vals
                    )
                    return
                # All good, replace the current trim settings
                self._trim = trim_vals
        except OSError as exc:
            logging.error("%s: Error restoring saved trim values: %s", self.LOG_PREFIX, exc)

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

    def _updateOscillators(self):
        """
        Updates the oscillators phase shift, amplitude, etc. based on the
        steering settings.

        NOTE! This method assumes that the caller has verified that
        self._steer_dir and self._steer_angle are valid values. No validation
        will be done.
        """
        if self._steer_dir in ['fwd', 'rev', 'rotr', 'rotl']:
            phase = globals().get(self._steer_dir.upper(), None)
            if phase is None:
                logging.error(
                    "Could not find phase dev in globals for %s",
                    self._steer_dir.upper()
                )
            self._phase = phase
            # We set the amplitude for all three oscillators in a list to make
            # it easier to apply when cycling over the servo oscillators later.
            # When going forward or reverse, the left/right amplitudes are the
            # current stroke value with no adjustments. The mid amplitude also
            # do not change
            amplitudes = [self._stroke, self._mid_ampl, self._stroke]

        # Adjust the stoke if we're going forward or reverse and the steer
        # angle is not 0. We assume the steer values have been validated by the
        # caller.
        if self._steer_angle and self._steer_dir in ['fwd', 'rev']:
            # What percentage of the angle from 0 to 90 is the steering angle
            # set at?
            turn_perc = (abs(self._steer_angle) * 100)/90
            # How much of the max stroke (amplitude) is this percentage?
            adj = (turn_perc * self.STROKE_MAX) // 100
            # We need to apply half this adjustment to each leg
            adj //= 2
            # If the angle is positive we make the right leg stroke shorter,
            # and the left leg stroke longer. If negative, we do it the other
            # way around
            if self._steer_angle > 0:
                stroke = [self._stroke + adj, self._stroke - adj]
            else:
                stroke = [self._stroke - adj, self._stroke + adj]
            # We may now be outside the min or max stroke, so we adjust if
            # needed.
            val = max(stroke)
            if val > self.STROKE_MAX:
                adj = val - self.STROKE_MAX
                stroke = [v - adj for v in stroke]
            val = min(stroke)
            if val < 0:
                adj = 0 - val
                stroke = [v + adj for v in stroke]
            # Translate the strokes into the 3 amplitudes
            amplitudes = [stroke[0], self._mid_ampl, stroke[1]]

        # Cycle over servo oscillators and set params.
        for idx, servo in enumerate(self._servos):
            # Set the phase shift
            servo.phase_shift = self._phase[idx]
            # Periods are the same for all
            servo.period = self._period
            # Amplitudes may be different depending on the steering angle, so
            # we set from the calculated values.
            servo.amplitude = amplitudes[idx]

    def _setupObstacleSensor(self, conf):
        """
        Sets up an HCSR04 Ultrasonic Sensor connected to sense obstacles.

        Args:
            conf (None/list): This is the sense argument received by the
                __init__ constructor. See the docstring there for more details.
        """
        # Nothing to do if there is no config
        if conf is None:
            return

        logging.info("Settings up obstacle sensor...")

        # We expect conf to be a list: [trigger_pin, echo_pin, max_range]
        # which is the exact args expected by the HCSR04 class.
        self._sense = HCSR04(*conf)

        # Create a task to continuously check for obstacles and update the
        # internal sensor moving average.
        uasyncio.create_task(
            self._sense.monitor(
                sample_delay=OBS_SAMPLE_DELAY,
                window=OBS_SAMPLE_WINDOW
            )
        )

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

        The trim degrees for each servo is given in a 3 element list. Any
        element that is None will not change that servo's trim.

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

        # Always save trim values locally after setting them
        self._saveTrim()

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

    @property
    def steer(self):
        """
        Gets current steering settings.

        Returns:
            The steering direction and angle:
            {
                'dir': one of 'fwd', 'rev', 'rot'r, 'rotl'
                'angle': current angle off the direction
            }

        """
        return {
            'dir': self._steer_dir,
            'angle': self._steer_angle
        }

    @steer.setter
    def steer(self, steer_val):
        """
        Changes steering settings.

        Args:
            steer_val (dict): The steering direction and/or angle:
                {
                    'dir': one of 'fwd', 'rev', 'rotr', 'rotl'
                    'angle': current angle off the direction
                }
                Either 'dir' or 'angle` can be omitted. Angle is optional at
                all times. If it is given, and the current dir is not 'fwd' or
                'rev', an error would be raised. IOW angel can only be
                specified for forward or reverse direction.

        Raises:
            ValueError with error message if direct param is invalid.
        """
        update_osc = False
        direct = steer_val.get('dir', None)
        angle = steer_val.get('angle', None)
        if direct is not None:
            if direct in ['fwd', 'rev', 'rotr', 'rotl']:
                self._steer_dir = direct
                # When getting any of these directional commands, we also
                # immediately reset the steering angle.
                self._steer_angle = 0
                update_osc = True
            else:
                raise ValueError(f"Invalid steering direction: {direct}")

        if angle is not None:
            if self._steer_dir not in ['fwd', 'rev']:
                raise ValueError(
                    "An angle can only be given when in 'fwd or "\
                    "'rev' direction"
                )
            if isinstance(angle, int) and (-90 <= angle <= 90):
                self._steer_angle = angle
                update_osc = True
            else:
                raise ValueError(f"Invalid steering angle: {angle}")

        # Now update the oscillators if needed
        if update_osc:
            self._updateOscillators()

    @property
    def speed(self):
        """
        Gets current "speed" which just a percentage value of the current
        oscillation period within the min and max period.

        Note that the longer/higher the period, the slower the speed and vice
        versa, meaning that the speed is inversely proportional to the period.

        Returns:
            The current speed percentage as an integer

        """
        # Calculate the "slowness" percentage for the current period out of the
        # max period allowed
        slowness = (self._period -self.PERIOD_MIN) * 100 // (self.PERIOD_MAX - self.PERIOD_MIN)
        # Return the inverted slowness to give the speed as a measure of
        # fastness
        return 100 - slowness

    @speed.setter
    def speed(self, val):
        """
        Sets the speed as a percentage of the maximum speed, or period,
        allowed.

        Args:
            val (int): A percentage between 0 and 100 of the allowed speed
            range.

        Raises:
            ValueError with error message if val param is invalid.
        """
        if not (isinstance(val, int) and (0 <= val <= 100)):
            raise ValueError(f"Invalid speed percentage value: {val}")

        # The speed is inversely proportional to period, so we need to first
        # get the "slowness" (inverse of the "fastness" which speed represents)
        # percentage before we can calculate the period.
        slowness = 100 - val

        # Now we can calculate what percentage this slowness will be of the
        # total allowed period, before offsetting it with the min period
        self._period = (
            slowness * (self.PERIOD_MAX - self.PERIOD_MIN) // 100
        ) + self.PERIOD_MIN

        # Cycle over servo oscillators and set period
        for servo in self._servos:
            servo.period = self._period

    @property
    def stroke(self):
        """
        Gets current stroke as a percentage of the self._stroke of
        self.STROKE_MAX.

        The stroke translates to the amplitude at which the left and right legs
        oscillate. The larger the stroke, further the legs move per cycle.

        In order to make setting this easier, we use a percentage of the max
        stroke value, as defined by STROKE_MIN_ANGL and STROKE_MAX_ANGL.

        Returns:
            The current stroke percentage as an integer
        """
        # Return the stoke percentage
        return self._stroke * 100 // self.STROKE_MAX

    @stroke.setter
    def stroke(self, val):
        """
        Sets the stroke as a percentage of STROKE_MAX.

        Args:
            val (int): A percentage between 0 and 100 used to calculate the
                final stroke value from STROKE_MAX.

        Raises:
            ValueError with error message if val param is invalid.
        """
        if not (isinstance(val, int) and (0 <= val <= 100)):
            raise ValueError(f"Invalid stroke percentage value: {val}")

        # Calculate the new stroke value
        self._stroke = val * self.STROKE_MAX // 100

        # If we set the amplitudes on the servos directly while there is a
        # steering angle set, we will mes up the steering. It's better to call
        # _updateOscillators since this will take steering into account,
        # although it also does some other unnecessary stuff. Refactoring
        # _updateOscillators could help in future.
        self._updateOscillators()

    @property
    def obstacle(self):
        """
        Property to check if there is an obstacle, and if so, how far ahead.

        Returns:
            -1 if no obstacle distance sensor is configured
            None if no obstacle is currently detected
            A value between 0 and the max sense range if an obstacle is
            detected
        """
        return -1 if self._sense is None else self._sense.avg()

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
