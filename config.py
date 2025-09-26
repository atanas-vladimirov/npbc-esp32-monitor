# config.py

# NTP Server
NTP_HOST = 'bg.pool.ntp.org'

# Remote Data-logging Server
REMOTE_POST_URL = 'http://172.16.1.1:8088/api/logData'

# ESP32 Static IP (Optional, leave as None for DHCP)
# To use, uncomment the line below and fill in your network details.
# STATIC_IP = ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')
STATIC_IP = None

# --- Timezone Configuration ---
# Set your local timezone offset from UTC in hours.
# For Bulgaria (EEST) this is +3. For winter time (EET) it would be +2.
TIMEZONE_OFFSET = 3

# --- OTA Update Configuration ---
# URL to your public GitHub repository
GITHUB_REPO = 'https://github.com/atanas-vladimirov/npbc-esp32-monitor'

# --- Pin Assignments ---
# Main Hardware SPI Bus (HSPI)
PIN_SPI_SCK = 18
PIN_SPI_MISO = 19

PIN_BME_SCK = 2     # SCL on BME/P 280 - green
PIN_BME_MISO = 15   # SDO on BME/P 280 - brown/white
PIN_BME_MOSI = 21   # SDA on BME/P 280 - brown

# Unique Chip Select (CS) pin for each SPI device
PIN_BME_CS = 22     # CSB on BME/P 280 blue/white
PIN_MAX6675_CS = 5

# Other Pins
PIN_DS18X20 = 4
PIN_UART2_TX = 17
PIN_UART2_RX = 16
