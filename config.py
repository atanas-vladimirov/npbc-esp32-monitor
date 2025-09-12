# config.py

# NTP Server
NTP_HOST = 'bg.pool.ntp.org'

# Remote Data-logging Server
REMOTE_POST_URL = 'http://172.16.1.1:8088/api/logData'

# ESP32 Static IP (Optional, leave as None for DHCP)
# To use, uncomment the line below and fill in your network details.
# STATIC_IP = ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')
STATIC_IP = None

# --- OTA Update Configuration ---
# URL to your public GitHub repository
GITHUB_REPO = 'https://github.com/atanas-vladimirov/npbc-esp32-monitor'

# --- Pin Assignments ---
# (Pin assignments remain the same as before)
PIN_SPI_SCK = 14    # SCL
PIN_SPI_MOSI = 13   # SDA
PIN_SPI_MISO = 12   # SDO
PIN_BME_CS = 15     # CSB

PIN_DS18X20 = 4

PIN_MAX6675_SO = 19
PIN_MAX6675_SCK = 18
PIN_MAX6675_CS = 5

PIN_UART2_TX = 17
PIN_UART2_RX = 16
