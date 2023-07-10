"""
Very minimal simulator for the hardware machine module when running under the
unix port of micropython.

This simulates just enough functionality to make the calls made from the
Hexapod class not fail, and thus allowing to fully simulate the Hexapod.
"""

#pylint: disable=missing-function-docstring,invalid-name

class Pin:
    """
    Very minimal Pin class simulator.
    """

    # TODO: This could be the wrong way around. Need to confirm....
    IN = 1
    OUT = 0

    def __init__(self, pin, value=None):
        self._value = value if value is not None else 0
        self._pin = pin

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0

    def value(self):
        return self._value

class PWM:
    """
    Very minimal PWM class simulator.
    """

    def __init__(self, dest, freq=0, duty=512):
        self._pin = dest
        self._freq = freq
        self._duty = duty

    def freq(self, val=None):
        if val is not None:
            self._freq = val
        return self._freq

    def duty(self, val=None):
        if val is not None:
            self._duty = val
        return self._duty
