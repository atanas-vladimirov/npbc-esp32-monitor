# DS18X20 driver for MicroPython.
# MIT license; Copyright (c) 2016-2021 Damien P. George

from micropython import const
import time

_CONVERT = const(0x44)
_RD_SCRATCH = const(0xBE)
_WR_SCRATCH = const(0x4E)
_COPY_SCRATCH = const(0x48)
_RECALL_E2 = const(0xB8)
_RD_POWER_SUPPLY = const(0xB4)

class DS18X20:
    def __init__(self, onewire):
        self.ow = onewire
        self.buf = bytearray(9)
        self.temp_last_convert = 0

    def scan(self):
        return [rom for rom in self.ow.scan() if rom[0] in (0x10, 0x22, 0x28, 0x3B, 0x42)]

    def convert_temp(self, rom=None):
        self.ow.reset()
        if rom is None:
            self.ow.writebyte(self.ow.SKIP_ROM)
        else:
            self.ow.select_rom(rom)
        self.ow.writebyte(_CONVERT)
        # For parasitic devices, wait for conversion to complete.
        if self.ow.readbit() == 0:
            self.temp_last_convert = time.ticks_ms()

    def read_scratch(self, rom):
        self.ow.reset()
        self.ow.select_rom(rom)
        self.ow.writebyte(_RD_SCRATCH)
        self.ow.readinto(self.buf)
        if self.ow.crc8(self.buf):
            raise Exception("CRC error")
        return self.buf

    def write_scratch(self, rom, buf):
        self.ow.reset()
        self.ow.select_rom(rom)
        self.ow.writebyte(_WR_SCRATCH)
        self.ow.write(buf)

    def read_temp(self, rom):
        # Wait for conversion to complete.
        if time.ticks_diff(time.ticks_ms(), self.temp_last_convert) < 750:
            # Parasitic devices can take up to 750ms to convert.
            time.sleep_ms(750 - time.ticks_diff(time.ticks_ms(), self.temp_last_convert))
        
        buf = self.read_scratch(rom)
        if rom[0] == 0x10:  # DS18S20
            if buf[1]:
                t = buf[0] >> 1 | 0x80
                t = -((~t + 1) & 0xFF)
            else:
                t = buf[0] >> 1
            return t - 0.25 + (buf[7] - buf[6]) / buf[7]
        else:  # DS18B20, DS1822
            t = buf[1] << 8 | buf[0]
            if t & 0x8000:  # sign bit set
                t = -((t ^ 0xFFFF) + 1)
            return t / 16