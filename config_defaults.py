# config_defaults.py — Default configuration values.
# This file is overwritten by OTA updates. Do NOT edit it on the device.
# To customize settings, override any value in config.py instead.

# NTP Server
NTP_HOST = 'bg.pool.ntp.org'

# Interval in seconds to re-sync the time (3600 = 1 hour)
NTP_SYNC_INTERVAL = 3600

# --- Timezone Configuration ---
# POSIX TZ string. Default: UTC (no offset, no DST)
TIMEZONE_POSIX = "EET-2EEST,M3.5.0/3,M10.5.0/4"

# Remote Data-logging Server (set to None to disable remote posting)
REMOTE_POST_URL = None  # 'http://172.16.1.111:8088/api/logData'

# ESP32 Static IP (None for DHCP)
# To use: STATIC_IP = ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')
STATIC_IP = None

# --- Optional network services ---
ENABLE_WEBREPL = True
ENABLE_FTP = True

# --- OTA Update Configuration ---
GITHUB_REPO = 'https://github.com/atanas-vladimirov/npbc-esp32-monitor'

# --- Pin Assignments ---
# MAX6675 K-Type thermocouple (SPI bus 1)
PIN_MAX6675_SCK = 5     # SCK on MAX6675
PIN_MAX6675_MISO = 7    # SO on MAX6675
PIN_MAX6675_CS = 6      # CS on MAX6675

# BME/BMP280 pressure/temp sensor (SPI bus 2)
PIN_BME_SCK = 9         # SCL on BME/P 280
PIN_BME_MISO = 8        # SDO on BME/P 280
PIN_BME_MOSI = 46       # SDA on BME/P 280
PIN_BME_CS = 3          # CSB on BME/P 280

# OneWire DS18X20 temperature sensor
PIN_DS18X20 = 4

# UART1 for debugging and logging
PIN_UART1_TX = 17
PIN_UART1_RX = 18