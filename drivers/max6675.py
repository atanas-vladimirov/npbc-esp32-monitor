# drivers/max6675.py
import time
from machine import Pin

class MAX6675:
    """Driver for the MAX6675 K-type thermocouple amplifier."""
    def __init__(self, sck_pin, cs_pin, so_pin):
        self.sck = Pin(sck_pin, Pin.OUT)
        self.cs = Pin(cs_pin, Pin.OUT)
        self.so = Pin(so_pin, Pin.IN)
        self.cs.on()

    def read(self):
        """Reads the temperature from the thermocouple in Celsius."""
        self.cs.off()
        time.sleep_us(10)
        value = 0
        for _ in range(12):
            self.sck.on()
            time.sleep_us(1)
            value = (value << 1) | self.so.value()
            self.sck.off()
            time.sleep_us(1)
        self.sck.on()
        time.sleep_us(1)
        error = self.so.value()
        self.sck.off()
        time.sleep_us(1)
        for _ in range(2):
            self.sck.on()
            time.sleep_us(1)
            self.sck.off()
            time.sleep_us(1)
        self.cs.on()
        if error:
            return float('NaN')
        return value * 0.25
