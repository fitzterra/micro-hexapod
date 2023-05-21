"""
Various mapping for the Wemos D1
"""
from micropython import const

# The GPIO pins to the D? mappings
D0 = const(16)
D1 = const(5)
D2 = const(4)
D3 = const(0)
D4 = const(2)
D5 = const(14)
D6 = const(12)
D7 = const(13)
D8 = const(15)

LED = D4

# I²C
SDA = const(D2)
SCL = const(D1)

# SPI
MCLK = const(D5)
MISO = const(D6)
MOSI = const(D7)
