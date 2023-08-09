"""
General config file
"""
from version import VERSION
import ujson

# This is the file name to use for storing the persisted config values.
PERSISTED = "config_p.txt"

conf = {
    # Set True to enable debugging
    #'debug': False,
    'debug': True,

    # The onboard LED pin
    # NOTE on the Wemos D1 the LED is connected to the high side, so we pass it
    #   as a negative pin number to invert the on/off state.
    #'led_pin': -D1_map.LED,
    'led_pin': 15,    # S2 Mini

    # The pins for the LEFT, MID and RIGHT servos
    #'pins': [D1_map.D5, D1_map.D6, D1_map.D7],
    'pins': [16, 18, 33],  # S2 Mini

    # The period is the same for all servos
    'period': 2000,

    # The stroke is the amplitude of the left and right servos, and designates
    # how far the legs moves per cycle (in degrees). The hexapod class will
    # have a min and max stroke that will clip this setting if out of bounds.
    'stroke': 30,

    # If and HCSR04 Ultrasonic Distance sensor is connected, this is where we
    # configure it. This value is either None for no sensor, or else a
    # 3 element list as: [trigger_pin, echo_pin, max_range]
    # See the HCSR04 class for details on why to keep the max_range as short as
    # possible in an asyncio app.
    'echo_sense': [37, 35, 300],

    # Web app
    'web_app': {
        'enabled': True,
    },
}

def getByDotKey(key, default=None):
    """
    Returns a config value from a doted key name representing the hierarchical
    config key value.

    Example:

    >>> run_web = getByDotKey('web_app.enabled')
    >>> if run_web is None:
    >>>     print("The web_app config may be borked...")
    >>> if run_web:
    >>>     startServer()

    Arg:
        key (str): The doted hierarchical name for the config key to get.

    Returns:
        The config value for the key if key is valid, or the default value
        otherwise.
    """
    dest = conf
    for k in key.split('.'):
        if not k in dest:
            return default
        # Only go deeper if we can
        if isinstance(dest[k], dict):
            dest = dest[k]
        else:
            # NOTE: This is no guarantee that we have come to the end of the
            # hierarchical key definition. We may have gotten to a point with
            # this key part that is not a dict anymore, but there may be more
            # parts, which indicates an invalid key. For now, we do not deal
            # with this, and we simply return what we can at this point.
            return dest[k]

    return default

def persist(dat):
    """
    Saves the data structure in dat to persistent local storage.

    This allow runtime configs to be saved between reboots.
    The dat structure is expected to follow the same structure as the global
    default conf structure. The idea is that first import of this module, any
    persisted config will be used to overwrite the default values in conf.

    The persisted data is saved in the file defined by PERSISTED, and is saved
    in JSON format.

    Returns:
        None if successful, or an error string otherwise.
    """
    try:
        with open(PERSISTED, 'w') as persisted:
            ujson.dump(dat, persisted)
    except Exception as exc: #pylint: disable=broad-except
        return "Error persisting: %s" % exc

    return None

def updateDict(source, dest):
    """
    Recursively updates the destination dictionary from the source dictionary.

    The destination can be any number of levels deep, but only exact key
    structure matches in source, will update equivalent values in destination.

    The idea is that the destination is some default dictionary structure, and
    the source is a structure resembling the destination, although the full
    structure does not necessarily have to be present in source. The parts in
    source that are there, must match the exact same levels and structures as
    in destination, or they will be ignored.

    This is when some default values are overridden and saved during runtime,
    and on new instantiation, the default destination is then updated from the
    saved source.
    """
    # Run through all the keys at the current level
    for key, val in source.items():
        # Any key in source that is not in destination, we ignore
        if key not in dest:
            continue

        # If the values for this key in the source is another dictionary, we
        # need to descend into that dict recursively and update the destination
        if isinstance(val, dict):
            # We only do this if the dest value is also a dict, or else we
            # ignore it
            if isinstance(dest[key], dict):
                updateDict(source[key], dest[key])
            continue

        # The values are not dictionaries, so we overwrite the destination from
        # the source
        dest[key] = val

def applyPersistance():
    """
    Updates conf from any persisted values in PERSISTED.
    """
    try:
        with open(PERSISTED, 'r') as in_file:
            p_conf = ujson.load(in_file)
            updateDict(p_conf, conf)
    except OSError:
        # Probably no file, so we skip
        pass

applyPersistance()
