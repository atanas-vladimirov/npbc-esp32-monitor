# drivers/bme280_driver.py
from micropython import const
from ustruct import unpack
import time

_CHIP_ID_BMP280 = const(0x58)
_CHIP_ID_BME280 = const(0x60)

_REG_CHIP_ID = const(0xD0)
_REG_RESET = const(0xE0)
_REG_CTRL_HUM = const(0xF2)
_REG_STATUS = const(0xF3)
_REG_CTRL_MEAS = const(0xF4)
_REG_CONFIG = const(0xF5)
_REG_DATA = const(0xF7)
_REG_CALIB_T_P = const(0x88)
_REG_CALIB_H1 = const(0xA1)
_REG_CALIB_H2 = const(0xE1)

class BME280:
    def __init__(self, i2c=None, spi=None, cs=None, addr=0x76):
        self.is_spi = spi is not None
        if self.is_spi:
            if cs is None: raise ValueError("Chip Select (cs) pin must be provided for SPI")
            self.spi, self.cs = spi, cs
            self.cs.init(self.cs.OUT, value=1)
        else:
            if i2c is None: raise ValueError("Either an i2c or spi object must be provided")
            self.i2c, self.addr = i2c, addr

        self.chip_id = self._read_reg(_REG_CHIP_ID)
        if self.chip_id not in [_CHIP_ID_BMP280, _CHIP_ID_BME280]:
            raise OSError("Invalid chip ID: 0x%x" % self.chip_id)
        self.is_bme280 = self.chip_id == _CHIP_ID_BME280

        self._load_calibration()
        self._set_mode()
        self.t_fine = 0

    def _read_reg(self, reg, nbytes=1):
        if self.is_spi:
            self.cs.off()
            self.spi.write(bytearray([reg | 0x80]))
            buf = self.spi.read(nbytes)
            self.cs.on()
            return buf[0] if nbytes == 1 else buf
        else:
            return self.i2c.readfrom_mem(self.addr, reg, nbytes)

    def _write_reg(self, reg, val):
        if self.is_spi:
            self.cs.off()
            self.spi.write(bytearray([reg & 0x7F, val]))
            self.cs.on()
        else:
            self.i2c.writeto_mem(self.addr, reg, bytearray([val]))

    def _load_calibration(self):
        c1 = self._read_reg(_REG_CALIB_T_P, 26)
        self.dig_T1 = unpack('<H', c1[0:2])[0]
        self.dig_T2 = unpack('<h', c1[2:4])[0]
        self.dig_T3 = unpack('<h', c1[4:6])[0]
        self.dig_P1 = unpack('<H', c1[6:8])[0]
        self.dig_P2 = unpack('<h', c1[8:10])[0]
        self.dig_P3 = unpack('<h', c1[10:12])[0]
        self.dig_P4 = unpack('<h', c1[12:14])[0]
        self.dig_P5 = unpack('<h', c1[14:16])[0]
        self.dig_P6 = unpack('<h', c1[16:18])[0]
        self.dig_P7 = unpack('<h', c1[18:20])[0]
        self.dig_P8 = unpack('<h', c1[20:22])[0]
        self.dig_P9 = unpack('<h', c1[22:24])[0]

        if self.is_bme280:
            self.dig_H1 = self._read_reg(_REG_CALIB_H1)
            c2 = self._read_reg(_REG_CALIB_H2, 7)
            self.dig_H2 = unpack('<h', c2[0:2])[0]
            self.dig_H3 = c2[2]
            self.dig_H4 = (c2[3] << 4) | (c2[4] & 0x0F)
            self.dig_H5 = (c2[5] << 4) | (c2[4] >> 4)
            self.dig_H6 = unpack('b', c2[6:7])[0]

    def _set_mode(self):
        if self.is_bme280:
            self._write_reg(_REG_CTRL_HUM, 0x01)
        self._write_reg(_REG_CTRL_MEAS, 0b01010111)
        self._write_reg(_REG_CONFIG, 0b10110000)

    @property
    def values(self):
        data_len = 8 if self.is_bme280 else 6
        data = self._read_reg(_REG_DATA, data_len)
        raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_hum = (data[6] << 8) | data[7] if self.is_bme280 else None
        
        temp = self._compensate_temp(raw_temp)
        press = self._compensate_press(raw_press)
        hum = self._compensate_hum(raw_hum) if self.is_bme280 else None
        return temp, press, hum

    def _compensate_temp(self, raw_temp):
        var1 = (raw_temp / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        var2 = ((raw_temp / 131072.0 - self.dig_T1 / 8192.0) ** 2) * self.dig_T3
        self.t_fine = int(var1 + var2)
        return self.t_fine / 5120.0

    def _compensate_press(self, raw_press):
        var1 = self.t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * self.dig_P6 / 32768.0 + var1 * self.dig_P5 * 2.0
        var2 = var2 / 4.0 + self.dig_P4 * 65536.0
        var1 = (self.dig_P3 * var1 * var1 / 524288.0 + self.dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.dig_P1
        if var1 == 0: return 0
        p = (1048576.0 - raw_press - var2 / 4096.0) * 6250.0 / var1
        var1 = self.dig_P9 * p * p / 2147483648.0
        var2 = p * self.dig_P8 / 32768.0
        return (p + (var1 + var2 + self.dig_P7) / 16.0) / 100.0

    def _compensate_hum(self, raw_hum):
        h = self.t_fine - 76800.0
        h = (raw_hum - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h)) * \
            (self.dig_H2 / 65536.0 * (1.0 + self.dig_H6 / 67108864.0 * h * \
            (1.0 + self.dig_H3 / 67108864.0 * h)))
        h = h * (1.0 - self.dig_H1 * h / 524288.0)
        return max(0.0, min(100.0, h))
