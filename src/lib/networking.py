"""
Provides all networking functionality
"""
import uasyncio
import network

async def connectToAP():
    """
    Connects to the configured network access point.

    In order to connect to an access point, a Python file called `netconfig.py`
    should be available in the import path. The contents of this file defines
    the AP access config and should look like this:

    ```
    SSID = "yourSSID"
    PASSWD = "your AP password"
    # DHCP hostname to set. If not defined or None or empty, no hostname will
    # be set.
    HOSTNAME = "hostname"
    # On ESP8266 the WiFi connection will always be set up on startup if it has
    # connected successfully before. In cases like this, including the FORCE
    # setting and setting it True will force a new connection even if the
    # interface is already active.
    FORCE = True or False
    ```

    If this file can be imported a connection to this SSID will be attempted.

    Args:
        force (bool): For ESP8266 the previous WiFi connection will
            automatically be tried again

    Returns:
        True if connected, False otherwise
    """
    try:
        import netconfig #pylint: disable=import-outside-toplevel
    except ImportError:
        print("No netconfig.py file file found. Aborting WiFi connection.")
        return False

    # Instantiate an object for accessing the station mode (to connect to WiFi)
    # interface.
    wlan = network.WLAN(network.STA_IF)

    # On ESP8266, the last WiFi connection will automatically be set again. If
    # the interface is active and we're not forcing, then we do not do any
    # further config.
    if not getattr(netconfig, "FORCE", False) and wlan.active():
        print("Interface is active and not forcing a connection.")
        return False


    # Get the hostname to set if any (also set to None on empty string)
    hostname = getattr(netconfig, "HOSTNAME") or None

    print(f"Setting up WiFi connection to {netconfig.SSID} as host {hostname}")
    # Connect
    wlan.active(True)
    # Short wait to get interface to "settle" on 1.19 see:
    # https://github.com/micropython/micropython/issues/8792#issuecomment-1161447599
    await uasyncio.sleep(0.5)
    if hostname:
        wlan.config(dhcp_hostname=hostname)
    wlan.connect(netconfig.SSID, netconfig.PASSWD)

    # Poll until we are active
    count = 0
    while not wlan.isconnected() and count < 20:
        await uasyncio.sleep(0.5)

    if count == 10:
        print(f"Could not connect to {netconfig.SSID}")
        return False

    print(f"Connected: {wlan.ifconfig()}")
    return True
