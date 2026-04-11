# config_defaults.py — Default configuration values.
# This file is overwritten by OTA updates. Do NOT edit it on the device.
# To customize settings, override any value in config.py instead.

# NTP Server
NTP_HOST = 'pool.ntp.org'

# Interval in seconds to re-sync the time (3600 = 1 hour)
NTP_SYNC_INTERVAL = 3600

# --- Timezone Configuration ---
# POSIX TZ string. Default: UTC (no offset, no DST)
TIMEZONE_POSIX = "UTC0"

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
PIN_MAX6675_SCK = 12
PIN_MAX6675_MISO = 13
PIN_MAX6675_CS = 14

# BME/BMP280 pressure/temp sensor (SPI bus 2)
PIN_BME_SCK = 8
PIN_BME_MISO = 17
PIN_BME_MOSI = 18
PIN_BME_CS = 16

# Other Pins
PIN_DS18X20 = 3
PIN_UART2_TX = 43
PIN_UART2_RX = 44
