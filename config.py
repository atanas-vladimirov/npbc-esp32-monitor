# config.py — User overrides (NOT overwritten by OTA updates).
# Only add settings here that differ from config_defaults.py.
# Any value defined here takes priority over the default.

# NTP Server
NTP_HOST = 'bg.pool.ntp.org'

# Timezone: Eastern European Time (UTC+2), DST = EEST (UTC+3)
TIMEZONE_POSIX = "EET-2EEST,M3.5.0/3,M10.5.0/4"

# --- Pin Assignments ---
# MAX6675 K-Type thermocouple (SPI bus 1)
PIN_MAX6675_SCK = 47
PIN_MAX6675_MISO = 20
PIN_MAX6675_CS = 21

# BME/BMP280 pressure/temp sensor (SPI bus 2)
PIN_BME_SCK = 8     # SCL - green
PIN_BME_MISO = 17   # SDO - brown/white
PIN_BME_MOSI = 18   # SDA - brown
PIN_BME_CS = 16     # CSB - blue/white

# Other Pins
PIN_DS18X20 = 3
PIN_UART2_TX = 11
PIN_UART2_RX = 12
