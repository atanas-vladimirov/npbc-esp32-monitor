# drivers/max6675.py
import time
from machine import Pin

class MAX6675:
    """
    Driver for the MAX6675 K-type thermocouple amplifier.
    This version is designed to use a shared hardware SPI bus.
    """
    def __init__(self, spi, cs_pin):
        """
        Initialize the sensor.
        :param spi: A configured machine.SPI object.
        :param cs_pin: The unique chip select GPIO pin number for this device.
        """
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT)
        self.cs.on() # Ensure CS is high (inactive) initially
        self._buf = bytearray(2) # Pre-allocate a 2-byte buffer for readings

    def read(self):
        """
        Reads the temperature from the thermocouple in Celsius.
        Returns float('NaN') on error.
        """
        self.cs.off() # Activate the sensor
        try:
            # The MAX6675 requires reading 2 bytes (16 bits)
            self.spi.readinto(self._buf)
        finally:
            self.cs.on() # Deactivate the sensor

        # Check for an open circuit error (bit 2 of the second byte)
        if self._buf[1] & 0x04:
            return float('NaN')

        # Combine the two bytes into a 16-bit value
        value = self._buf[0] << 8 | self._buf[1]

        # The temperature data is in bits 3-15. We shift right by 3.
        temp_data = value >> 3

        # The value is a 12-bit number, and the temperature is this value * 0.25
        return temp_data * 0.25
