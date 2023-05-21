"""
General config file
"""
from micropython import const
import lib.wemosD1_maps as D1_map

# This is the file name to use for storing the persisted config values.
PERSISTED = "config_p.txt"

conf = {
    # Set True to enable debugging
    #'debug': False,
    'debug': True,

    # The servo pins - these are the actual GPIO pin numbers
    'servo': {
        'left': {
            'pin': D1_map.D5,
            'trim': 0,
            'amplitude': 30,
            'phase_shift': 0,
        },
        'mid': {
            'pin': D1_map.D6,
            'trim': 5,
            'amplitude': 10,
            'phase_shift': 90,
        },
        'right': {
            'pin': D1_map.D7,
            'trim': 0,
            'amplitude': 30,
            'phase_shift': 0,
        },
    },

    # The period is the same for all servos
    'period': 2000,

    # Web app
    'web_app': {
        'enabled': True,
    },
}


def expandFormats(topics):
    """
    Expand any strings that may have format specifiers in the config section
    passed in.

    This is only used for the MQTT topic names at the moment to allow easier
    specification of a topics hierarchy - over engineered, but fun nonetheless
    :-)
    """
    # Expand topics that contain format() specifiers.
    # NOTE - In order to ensure we can have multiple levels of adding format
    # specifiers, we over-engineer this thing by doing the following:
    # * Loop forever until we break out forcibly:
    #   * Get all topics as key:vals for only those topics that do not contain any
    #     '{' character, i.e. does not have any replaceable parameters.
    #   * Cycle though all topics, applying only the dict of key:topics that we got
    #     before that does not have any replaceable values in the topic.
    #   * If there were any changes, set a breakout flag to False so that we run
    #     through again until no more changes were made
    #   * After the replaceable params have been applied to all topics, and there
    #     were no changes, (breakout flag is True), then break out of the forever
    #     loop with force, else run through again
    while True:
        break_out = True  #pylint: disable=invalid-name
        for k in topics:
            if not '{' in topics[k]:
                continue
            old = topics[k]
            topics[k] = topics[k].format(**topics)
            # If anything changed, don't break out yet
            if break_out and topics[k] != old:
                break_out = False
        if break_out:
            break

def updateConf(item, val, autotype=False, persist=False):
    """
    Allows a config value (in conf) to be changed, and optionally also
    persisted between reboots.

    The item to be set is the name of the config key using a dotted type
    notation. For example setting conf['valve']['ppl'] to 77 and having
    it persist, the call will be:

        updateConf('valve.ppl', 77, persist=True)

    Args:
        item (str): The doted hierarchical name for the config key to set.
        val (any) : The value to set. If persistence is needed, this value must
            evaluate to a string representation using the repr(val) function,
            and this string version must be able to be converted to original
            value using eval later. In other words, this must be True:
                val == eval(repr(val))
        autotype (bool): If True, and the value being set is not of the same
            type as the current value, and attempt will be made auto convert
            `val` to the same type as the value currently has. This is mainly
            helpful where the value is being set from an API that posts the new
            value as string while it should be and int or similar. This only
            works for simple types.
        persist (bool): If True the item key and a string representation of the
            value will be written to the file set by the PERSISTED constant.
            All these persisted values will be read in and overwrite their
            respective config values everytime this module is imported.

    Returns:
        None on success, or else and error message indicating any reason why
        the change could not be done.
    """
    #print("Gonna set conf: %s = %s (%d)" % (item, val, persist))
    # Find the relevant value key in conf to change
    dest = conf
    key = None
    for k in item.split('.'):
        if not k in dest:
            return f"Not a valid key notation at {k} for {item}"
        # Only go deeper if we can
        if not isinstance(dest[k], dict):
            key = k
            break
        dest = dest[k]

    # If key is None, the last part in item points to a dict, meaning that val
    # is a replacement for that whole dict - we do not currently support this.
    if key is None:
        return "Key notation points to dict which is not supported."

    # Need to do an auto type conversion?
    if autotype and type(val) != type(dest[key]):
        val = type(dest[key])(val)

    # Set the new value
    dest[key] = val

    # Persist?
    if not persist:
        return None

    #pylint: disable=invalid-name

    # Read all current persisted entries if any
    persisted = []
    try:
        with open(PERSISTED, "r") as f:
            persisted = f.readlines()
    except OSError as exc:
        # Error number 2 is ENOENT, meaning file does not exist, and this OK,
        # but anything else is an error
        # other error.
        if exc.errno != 2:
            return "Error persisting: %s" % exc

    #print("Persisted: ", persisted)

    # Now we will overwrite or create PERSISTED file and rewrite it, updating
    # the changed entry, or adding it if we do not already have it.
    try:
        with open(PERSISTED, 'w') as f:
            updated = False
            # Cycle through all persisted entries, updating this one if it is
            # there already, and then writing each line out.
            # We store the item as 'item: repr(val)' in the persistence file.
            for l in persisted:
                if l.startswith('%s:' % item):
                    l = "%s: %s\n" % (item, repr(val))
                    updated = True
                f.write(l)
                #print("Wrote to PERSISTED:", l)

            if not updated:
                f.write("%s: %s\n" % (item, repr(val)))
                #print("Wrote new item to PERSISTED:")

    except Exception as exc: #pylint: disable=broad-except
        return "Error persisting: %s" % exc

    return None

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

def applyPersistance():
    """
    Updates conf from any persisted values in PERSISTED.
    """
    #pylint: disable=invalid-name,eval-used
    try:
        with open(PERSISTED, 'r') as f:
            for l in f.readlines():
                #print("Line: %s" % l)
                # Does it look like something we can use?
                parts = l.rstrip().split(': ')
                if len(parts) == 2:
                    #print("Its configable...")
                    updateConf(parts[0], eval(parts[1].strip()), autotype=False, persist=False)
    except OSError:
        # Probably no file, so we skip
        pass

applyPersistance()
