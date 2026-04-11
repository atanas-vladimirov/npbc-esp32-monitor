# boot.py
import gc
import network
import ntptime
import machine
import time
from lib.config_loader import config

try:
    import secrets
except ImportError:
    print("ERROR: 'secrets.py' file not found. Please create it with your credentials.")
    secrets = None

machine.freq(240000000)

if getattr(config, 'ENABLE_WEBREPL', True):
    import webrepl
    if secrets and hasattr(secrets, 'WEBREPL_PASS'):
        webrepl.start(password=secrets.WEBREPL_PASS)
        print("WebREPL started with password from secrets.py.")
    else:
        webrepl.start()
        print("WebREPL started with default or no password.")
else:
    print("WebREPL disabled.")


def connect_wifi():
    """Connects to WiFi and sets the system time via NTP."""
    if not (secrets and hasattr(secrets, 'WIFI_SSID')):
        print("Cannot connect to WiFi, secrets not available or incomplete.")
        return

    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('Connecting to network...')
        sta_if.active(True)
        sta_if.config(pm=sta_if.PM_NONE)

        if config.STATIC_IP:
            sta_if.ifconfig(config.STATIC_IP)

        sta_if.connect(secrets.WIFI_SSID, secrets.WIFI_PASS)

        timeout = 15
        while not sta_if.isconnected() and timeout > 0:
            print('.', end='')
            time.sleep(1)
            timeout -= 1

    if sta_if.isconnected():
        print('\nNetwork connected!')
        print('IP Address:', sta_if.ifconfig()[0])

        ntptime.host = config.NTP_HOST
        try:
            ntptime.settime()
            print('Time synchronized')
        except Exception as e:
            print(f'Time sync failed: {e}')
    else:
        print('\nFailed to connect to WiFi.')

connect_wifi()

gc.collect()
