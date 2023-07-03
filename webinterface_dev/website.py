#!/usr/bin/env python3
"""
Development server for device web interface.
"""

import logging

from bottle import (
    route, get, post, run, request, static_file, response, json_dumps
)


from version import VERSION


class Sim:
    """
    Simulates the various hexapod calls available
    """

    PERIOD_MAX = 3000
    PERIOD_MIN = 500
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

    LOG_PREFIX = "SIM"

    def __init__(self):
        """
        Class init.
        """
        self._period = 2000
        self._stroke = 30
        self._paused = True
        self._trim = [0, 0, 0]
        self._steer_dir = 'fwd'
        self._steer_angle = 0

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
        # Run over each servo, setting both the self._trim element for the
        # servos, as well as the actual servo trim
        for idx, trim_val in enumerate(trim):
            if trim_val is None:
                continue
            # Set the servo trim and our trim value
            self._trim[idx] = trim_val

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
        direct = steer_val.get('dir', None)
        angle = steer_val.get('angle', None)
        if direct is not None:
            if direct in ['fwd', 'rev', 'rotr', 'rotl']:
                self._steer_dir = direct
                # When getting any of these directional commands, we also
                # immediately reset the steering angle.
                self._steer_angle = 0
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
            else:
                raise ValueError(f"Invalid steering angle: {angle}")

    @property
    def speed(self):
        """
        Speed property getter.

        Returns the current speed as a percentage of current period between the
        min and max allowed period.

        Returns:
            The speed percentage as an int
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

    def saveParams(self):
        """
        simulates saving the current parameters to persistent storage.
        """
        return self.getParams()


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

@route('/favicon.ico')
def favicon():
    """
    Serves the favicon.ico file.
    """
    return static_file("favicon.ico", root='./static')

@route('/')
def index():
    """
    Main entry point
    """
    return static_file('index.html', root='./static')

@route('/trim', method=["GET", "POST"])
def trim():
    """
    Gets or sets the servo trim values.

    GET:
        Returns the current trim values as:
            [left trim, mid trim, right trim]

    POST request data:
        A list with the trim values for the servos:
            [left trim, mid trim, right trim]
        Any of the 3 trim values can be None (null) to not set the trim for
        that servo.
        Optionally, this could also be a JSON object with a 'trim' keyword and
        value the list of trim settings, and an optional 'center' boolean:
            {
                "trim": [left trim, mid trim, right trim],
                "center": True/False # If true, servos will also be centered
                            with new trim values.
            }

    POST response:
        If no errors, returns the same as for the GET request.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        # Because bottle will only auto convert a dict to JSON response, we need
        # to do it ourselves if we only return a list, but still want a JSON
        # response.
        response.set_header('Content-Type', 'application/json')
        return json_dumps(sim.trim)

    # By default we do not also center servos
    center = False

    # Must be a POST, body could be a list or dict
    trim_list = request.json
    # If it's a dict, we expect the 'trim' key, from which we will then take
    # the value which is expected to the trim list.
    if isinstance(trim_list, dict):
        if not "trim" in trim_list:
            return {"errors": ["No 'trim' key in parameters."]}
        # Before changing trim_list from a dict to the actual trim values, get
        # the center value out if any
        center = trim_list.get("center", False)
        trim_list = trim_list['trim']

    if not isinstance(trim_list, list) or len(trim_list) != 3:
        return {"errors": ["Expect a list of three trim values."]}

    # Set t he trims
    sim.trim = trim_list

    # Do we also center?
    if center:
        sim.centerServos(True)

    # See comment for GET above about returning a list a JSON
    response.set_header('Content-Type', 'application/json')
    return json_dumps(sim.trim)

@route('/pause', method=["POST"])
def pause():
    """
    Pauses the hexapod if it is currently running

    POST:
        An empty body
    """
    sim._paused = True

@route('/run', method=["POST"])
def runServos():
    """
    Starts or unpauses the hexapod if it was paused.

    POST:
        An empty body
    """
    sim._paused = False

@route('/steer', method=["GET", "POST"])
def steer():
    """
    Gets or sets the steering direction.

    GET:
        Returns the current steering values as:
            {
                'dir': one of 'fwd', 'rev', 'rotr', 'rotl'
                'angle': current angle off the direction
            }

    POST request data:
        {
            'dir': 'fwd', 'rev', 'rotr', 'rotl'
            'angle': angle off the 'fwd' or 'rev' direction
        }

        Both `dir` and `angle` are optional. Angle will be ignored if the
        current direction is not 'fwd' or 'rev'.

    POST response:
        If no errors, returns the same as for the GET request.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return sim.steer

    # Must be a POST, body could be a list or dict
    params = request.json
    if not ('dir' in params or 'angle' in params):
        return {"errors": ["At least one of 'dir' or 'angle' keys required."]}

    try:
        sim.steer = params
    except Exception as exc:
        return {"errors": [str(exc)]}

    return sim.steer

@route('/speed', method=["GET", "POST"])
def speed():
    """
    Gets or sets the oscillation speed, or period.

    GET:
        Returns the current speed value as a percentage of the total allowed
        period:
        {"speed": speed percentage as integer (0 - 100)"

    POST request data:
        {"speed": speed percentage as integer (0 - 100)"

    POST response:
        If no errors, returns the same as for the GET request. Note that the
        speed percentage returned could be slightly different to the value used
        to set it. This is due to rounding errors when sticking to integer
        percentages.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return {"speed": sim.speed}

    # Must be a POST, body could be a list or dict
    dat = request.json
    # We expect the 'speed' key, from which we will then take
    # the actual speed value
    if isinstance(dat, dict):
        if not "speed" in dat:
            return {"errors": ["No 'speed' key in parameters."]}

    dat = dat["speed"]

    # Allow it to be passed in as a string
    if isinstance(dat, str):
        try:
            dat = int(dat)
        except ValueError as exc:
            return {"errors": [str(exc)]}

    try:
        sim.speed = dat
    except Exception as exc:
        return {"errors": [str(exc)]}

    return {"speed": sim.speed}

@route('/stroke', method=["GET", "POST"])
def stroke():
    """
    Gets or sets the oscillation amplitude for the left and right legs as a
    a percentage of the max stroke defined for them.

    GET:
        Returns the current stroke value as a percentage of the maximum allowed
        stroke or amplitude setting for the left/right legs:
        {"stroke": stroke percentage as integer (0 - 100)"

    POST request data:
        {"stroke": stroke percentage as integer (0 - 100)"

    POST response:
        If no errors, returns the same as for the GET request. Note that the
        stroke percentage returned could be slightly different to the value used
        to set it. This is due to rounding errors when sticking to integer
        percentages.
        If any errors, returns:
            {"errors": [error message(s)]}
    """
    if request.method == "GET":
        return {"stroke": sim.stroke}

    # Must be a POST, body could be a list or dict
    dat = request.json
    # We expect the 'stroke' key, from which we will then take
    # the actual stroke value
    if isinstance(dat, dict):
        if not "stroke" in dat:
            return {"errors": ["No 'stroke' key in parameters."]}

    dat = dat["stroke"]

    # Allow it to be passed in as a string
    if isinstance(dat, str):
        try:
            dat = int(dat)
        except ValueError as exc:
            return {"errors": [str(exc)]}

    try:
        sim.stroke = dat
    except Exception as exc:
        return {"errors": [str(exc)]}

    return {"stroke": sim.stroke}

@route('/center_servos', method=["POST"])
def centerServos():
    """
    Sets all servos to the center position (90°), with or without the current
    trim settings.

    NOTE: This will force the paused state if not already paused.

    POST request data:
        "with_trim": boolean

    The post data is optional and if not supplied, "with_trim" will default to
    True, meaning that the current trim settings will be taken into account
    when centering the servos.

    POST response:
        {errors": [One or more error strings if error]}
    """
    resp = {"errors": []}
    sim._paused = True

    return resp

@route('/mem')
def memInfo():
    """
    Returns the current memory status.

    GET:
        Returns:
            {"alloc": int, "free": int}
    """
    return {"alloc": 1000, "free": 1000}

@route('/version')
def version():
    """
    Returns the current app version

    GET:
        Returns:
            {"version": 'major.minor.patch'}
    """
    return {"version": VERSION}

run(host='0.0.0.0', port=5000, reloader=True, debug=True)
