import gc
import time
from machine import SoftI2C, Pin, Timer
import network
import micropython
import urequests as requests
import json

import picoweb
import onewire
import ds18x20
import uartworker0
import bmp280 as bmp
from max6675 import MAX6675

res = 0

# get the IP address
ip = network.WLAN(network.STA_IF).ifconfig()[0]

micropython.alloc_emergency_exception_buf(100)

# max6675 K-type thermocouple
def ktype():
    so = Pin(19, Pin.IN)
    sck = Pin(18, Pin.OUT)
    cs = Pin(5, Pin.OUT)
    max6675 = MAX6675(sck, cs, so)
    result = {'KTYPE': max6675.read()}
    return result


# BMP280
def bosh():
    i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=10000)

    try:
        b = bmp.BMP280(i2c)
        b.use_case(bmp.BMP280_CASE_WEATHER)
        b.oversample(bmp.BMP280_OS_HIGH)
        b.temp_os = bmp.BMP280_TEMP_OS_8
        b.press_os = bmp.BMP280_PRES_OS_4
        result = {'TBMP': round(b.temperature, 2), 'PBMP': (b.pressure/100)}

    except OSError:
        return {'TBMP': 0, 'PBMP': 0}

    return result


# ds18s20
def ow():
    ds_pin = Pin(4)
    ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
    roms = ds_sensor.scan()
    ds_sensor.convert_temp()
    time.sleep_ms(750)
    result = {'TDS18': round(ds_sensor.read_temp(roms[0]), 2)}
    return result


def collect_data(timer):
    try:

        returning_watter = ow()
        exhaust_gases = ktype()
        external_wheather = bosh()
        rb20 = uartworker0.run()

        result = returning_watter.copy()
        result.update(exhaust_gases)
        result.update(external_wheather)
        result.update(rb20)
        #print(result)

        try:
            r = requests.post('http://172.16.1.1:8089/post', json=result)

        except:
            print("The host is unreachable")

        global res
        res = result
        result = {}
        gc.collect()

    except Exception as e:
        err = e

# <web repl login>
# import sys
# sys.print_exception(err)

timer1 = Timer(1)
timer1.init(period=30000, mode=Timer.PERIODIC, callback=collect_data)

# to stop the timer
# timer1.deinit()

def mode(x):
    return {
        '0': 'Standby',
        '1': 'Auto',
        '2': 'Timer',
    }[x]


def state(x):
    return {
        '0': 'CH Priorit',
        '1': 'DHW Priority',
        '2': 'Parallel Pumps',
        '3': 'Summer Mode',
    }[x]


def power(x):
    return {
        '0': '',
        '1': '/ Suspend',
        '2': '/ Power 1',
        '3': '/ Power 2',
        '4': '/ Power 3',
    }[x]


def status(x):
    return {
        '0': 'Idle',
        '1': 'Fan Cleaning',
        '2': 'Cleaner',
        '3': 'Wait',
        '4': 'Loading',
        '5': 'Heating',
        '6': 'Ignition1',
        '7': 'Ignition2',
        '8': 'Unfolding',
        '9': 'Burning',
        '10': 'Extinction',
        '11': 'Standby/Extinct',
    }[x]


def pump(x):
    return {
        'False': 'Off',
        'True': 'On',
    }[x]


app = picoweb.WebApp(__name__)

@app.route("/")
def index(req, resp):

    global res
    data = res
    if isinstance(data['Mode'], int):
        data['Mode'] = mode(str(data.get('Mode')))
        data['State'] = state(str(data.get('State')))
        data['Power'] = power(str(data.get('Power')))
        data['Status'] = status(str(data.get('Status')))
        data['DHWPump'] = pump(str(data.get('DHWPump')))
        data['CHPump'] = pump(str(data.get('CHPump')))

    yield from picoweb.start_response(resp)
    yield from app.render_template(resp, "index.html", (data,))

@app.route("/setModeAndPriority")
def setModeAndPriority(req, resp):
    method = req.method
    print("Method was:" + method)

    if req.method == "POST":
        yield from req.read_form_data()
        
#        print('req.__dict__')
#        print(req.__dict__)
#        print("")
        
        data = req.form
        import setModeAndPriority
        sp = setModeAndPriority.SerialProcessSet(int(data["Mode"]),int(data["Priority"]))
        sp.run()

    else:
        req.parse_qs()

    yield from picoweb.start_response(resp)
    yield from resp.awrite("OK")
    yield from resp.awrite("\r\n")


app.run(debug=True, host = ip, port = 80)
