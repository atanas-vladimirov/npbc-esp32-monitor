# main.py
import gc
import json
import uasyncio as asyncio
import urequests as requests
from machine import Pin, SPI, reset
import network
import time
import ntptime
import math

# Web framework
from microdot import Microdot, Response, send_file

# App-specific imports
from lib.config_loader import config
from lib.npbc import NPBCController
from lib.ota import OTAUpdater
from lib.scheduler import Scheduler
from drivers.max6675 import MAX6675
from drivers.bme280_driver import BME280
import onewire
import ds18x20
import localPTZtime
from lib.log import log, setup as log_setup

# --- Setup Logging ---
log_setup(localPTZtime.tztime, config.TIMEZONE_POSIX)

# --- Capture Boot Time ---
boot_time = time.time()

# --- Software Version (from main.json) ---
_sw_version = '?'
try:
    with open('main.json', 'r') as f:
        _sw_version = json.load(f).get('version', '?')
except Exception:
    pass

# --- State Management ---
app_state = {
    'burner': {'status': 'Initializing...'},
    'sensors': {'status': 'Initializing...'},
    'last_update': 'Never'
}

# --- OTA Updater Instance ---
ota_updater = OTAUpdater(config.GITHUB_REPO, main_dir='.')

# --- Scheduler Instance ---
scheduler = Scheduler()

# --- Sensor Reading Classes ---
class SensorReader:
    def __init__(self):

        spi1 = SPI(1, baudrate=100000,
                  sck=Pin(config.PIN_MAX6675_SCK),
                  miso=Pin(config.PIN_MAX6675_MISO))

        spi2 = SPI(2, baudrate=100000,
                  sck=Pin(config.PIN_BME_SCK),
                  mosi=Pin(config.PIN_BME_MOSI),
                  miso=Pin(config.PIN_BME_MISO))

        try:
            bme_cs = Pin(config.PIN_BME_CS)
            self.bme = BME280(spi=spi2, cs=bme_cs)
            log(f"Detected Chip ID: {hex(self.bme.chip_id)}. Is BME280: {self.bme.is_bme280}")
        except OSError as e:
            log(f"BME/BMP sensor not found. Continuing without it. Error: {e}")
            self.bme = None

        self.k_type = MAX6675(spi=spi1, cs_pin=config.PIN_MAX6675_CS)

        ds_pin = Pin(config.PIN_DS18X20)
        self.ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
        roms = self.ds_sensor.scan()
        self.ds_rom = roms[0] if roms else None

    async def read_all(self):
        data = {}

        if self.bme:
            data['BME_TYPE'] = 'BME280' if self.bme.is_bme280 else 'BMP280'
            try:
                temp, press, hum = self.bme.values
                data['TBMP'] = round(temp, 2)
                data['PBMP'] = round(press, 2)
                if hum is not None:
                    data['HUM'] = round(hum, 2)
            except Exception as e:
                log(f"Error reading BME/BMP sensor: {e}")
                data['TBMP'], data['PBMP'] = 0, 0
        else:
            data['BME_TYPE'] = 'N/A'
            data['TBMP'] = 0
            data['PBMP'] = 0

        if self.ds_rom:
            self.ds_sensor.convert_temp()
            await asyncio.sleep_ms(750)
            data['TDS18'] = round(self.ds_sensor.read_temp(self.ds_rom), 2)
        else:
            data['TDS18'] = 0

        k_type_temp = self.k_type.read()
        if k_type_temp is not None and math.isnan(k_type_temp):
            data['KTYPE'] = 0.0
            log("K-Type sensor returned NaN (check wiring). Defaulting to 0.0.")
        else:
            data['KTYPE'] = k_type_temp

        return data

# --- Main Application Tasks ---
async def data_collector_task(npbc, sensors):
    while True:
        log("Collecting data...")
        try:
            async def _get_burner():
                try:
                    return await npbc.get_general_information()
                except Exception as e:
                    log(f"Burner communication error: {e}")
                    return None

            sensor_data, burner_response_object = await asyncio.gather(
                sensors.read_all(), _get_burner()
            )

            burner_data = {}
            if burner_response_object:
                burner_data = burner_response_object.to_dict()

            if not burner_data:
                log("Burner data unavailable, continuing with sensor data only.")

            utc_now = time.time()
            local_time_tuple = localPTZtime.tztime(utc_now, config.TIMEZONE_POSIX)

            app_state['burner'] = burner_data if burner_data else {'status': 'Unavailable'}
            app_state['sensors'] = sensor_data
            app_state['last_update'] = f"{local_time_tuple[3]:02d}:{local_time_tuple[4]:02d}:{local_time_tuple[5]:02d}"

            full_data = burner_data.copy()
            full_data.update(sensor_data)

            log(f"Data: {full_data}")

            if config.REMOTE_POST_URL and burner_data:
                try:
                    response = requests.post(
                        config.REMOTE_POST_URL,
                        json=full_data,
                        headers={'content-type': 'application/json'}
                    )

                    if response.status_code == 200:
                        log("Data posted successfully.")
                    else:
                        log(f"Server responded with status {response.status_code}")

                    response.close()

                except Exception as e:
                    log(f"Host unreachable or request failed: {e}")

        except Exception as e:
            log(f"Error in data collection: {e}")

        gc.collect()
        await asyncio.sleep(30)

# --- Scheduler Task ---
async def scheduler_task(npbc, sensor_reader):
    while True:
        try:
            utc_now = time.time()
            current_time = localPTZtime.tztime(utc_now, config.TIMEZONE_POSIX)
            current_hour = current_time[3]
            current_minute = current_time[4]
            current_day_of_week = current_time[6]

            current_temp = app_state.get('sensors', {}).get('TBMP', 0)

            schedules = scheduler.get_schedules()

            for sched in schedules:
                if not sched.get('enabled', False):
                    continue

                if not sched['days'][current_day_of_week]:
                    continue

                condition = sched.get('temp_condition', 'none')
                threshold = sched.get('temp_threshold', 0)
                temp_ok = False

                if condition == 'none':
                    temp_ok = True
                elif condition == 'below' and current_temp < threshold:
                    temp_ok = True
                elif condition == 'above' and current_temp > threshold:
                    temp_ok = True

                on_time_str = sched.get('on_time')
                if on_time_str:
                    try:
                        on_hour, on_minute = map(int, on_time_str.split(':'))
                        if on_hour == current_hour and on_minute == current_minute:
                            log(f"Scheduler: Matched ON time for '{sched['name']}'")
                            if temp_ok:
                                log(f"Executing ON action for '{sched['name']}'")
                                await npbc.set_mode_and_priority(1, sched['priority_on'])
                            else:
                                log(f"Temp condition NOT met for '{sched['name']}' ON. Skipping.")
                    except ValueError:
                        pass

                off_time_str = sched.get('off_time')
                if off_time_str:
                    try:
                        off_hour, off_minute = map(int, off_time_str.split(':'))
                        if off_hour == current_hour and off_minute == current_minute:
                            log(f"Scheduler: Matched OFF time for '{sched['name']}'")
                            if temp_ok:
                                log(f"Executing OFF action for '{sched['name']}'")
                                await npbc.set_mode_and_priority(0, 0)
                            else:
                                log(f"Temp condition NOT met for '{sched['name']}' OFF. Skipping.")
                    except ValueError:
                        pass

        except Exception as e:
            log(f"Error in scheduler task: {e}")

        await asyncio.sleep(60)

# --- NTP SYNC TASK ---
async def ntp_sync_task():
    while True:
        await asyncio.sleep(config.NTP_SYNC_INTERVAL)
        try:
            log("Performing periodic NTP time sync...")
            ntptime.host = config.NTP_HOST
            ntptime.settime()
            log("Time re-synchronized successfully.")
        except Exception as e:
            log(f"Periodic NTP sync failed: {e}")

# --- Helper Functions ---
def get_wifi_rssi():
    try:
        sta = network.WLAN(network.STA_IF)
        if sta.isconnected():
            return sta.status('rssi')
    except Exception:
        pass
    return None

def format_uptime(seconds):
    try:
        days = seconds // 86400
        seconds %= 86400
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        days, hours, minutes, seconds = int(days), int(hours), int(minutes), int(seconds)
        if days > 0:
            return f"{days}d, {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return "..."

def format_burner_data(data):
    if not data or 'Mode' not in data: return data
    modes = {0: 'Standby', 1: 'Auto', 2: 'Timer'}
    states = {0: 'CH Priority', 1: 'DHW Priority', 2: 'Parallel Pumps', 3: 'Summer Mode'}
    powers = {0: 'Off', 1: 'Suspend', 2: 'Power 1', 3: 'Power 2', 4: 'Power 3'}
    statuses = {0: 'Idle', 1: 'Fan Cleaning', 2: 'Cleaner', 3: 'Wait', 4: 'Loading', 5: 'Heating', 6: 'Ignition1', 7: 'Ignition2', 8: 'Unfolding', 9: 'Burning', 10: 'Extinction', 11: 'Standby/Extinct'}
    formatted = data.copy()
    formatted['Mode'] = modes.get(data.get('Mode'), 'Unknown')
    formatted['State'] = states.get(data.get('State'), 'Unknown')
    formatted['Power'] = powers.get(data.get('Power'), 'Unknown')
    formatted['Status'] = statuses.get(data.get('Status'), 'Unknown')
    formatted['DHWPump'] = "On" if data.get('DHWPump') else "Off"
    formatted['CHPump'] = "On" if data.get('CHPump') else "Off"
    return formatted

# --- Web Server Setup ---
app = Microdot()
Response.default_content_type = 'text/html'
npbc_controller = None

@app.route('/')
async def index(request):
    return send_file('templates/index.html')

@app.route('/static/<path:path>')
def static(request, path):
    return send_file(f'static/{path}')

@app.route('/api/data')
async def api_data(request):
    current_uptime_seconds = time.time() - boot_time

    full_state = {
        'burner': format_burner_data(app_state.get('burner', {})),
        'sensors': app_state.get('sensors', {}),
        'last_update': app_state.get('last_update'),
        'esp32': {
            'uptime': format_uptime(current_uptime_seconds),
            'version': _sw_version,
            'rssi': get_wifi_rssi(),
            'free_mem': gc.mem_free(),
            'ip': network.WLAN(network.STA_IF).ifconfig()[0],
        }
    }
    return Response(json.dumps(full_state), headers={'Content-Type': 'application/json'})

@app.route('/api/schedules', methods=['GET'])
async def get_schedules(request):
    return Response(json.dumps(scheduler.get_schedules()), headers={'Content-Type': 'application/json'})

@app.route('/api/schedules', methods=['POST'])
async def save_schedule(request):
    data = request.json
    schedule_id = data.get('id')
    if schedule_id:
        updated = scheduler.update_schedule(schedule_id, data)
        return Response(json.dumps(updated), 200)
    else:
        new_sched = scheduler.add_schedule(data)
        return Response(json.dumps(new_sched), 201)

@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
async def delete_schedule(request, schedule_id):
    if scheduler.delete_schedule(int(schedule_id)):
        return Response({'status': 'ok'}, 200)
    else:
        return Response({'status': 'not_found'}, 404)

@app.route('/api/settings', methods=['POST'])
async def api_settings(request):
    global npbc_controller
    data = request.json
    mode, priority = data.get('mode'), data.get('priority')

    if mode is not None and priority is not None:
        success = await npbc_controller.set_mode_and_priority(int(mode), int(priority))

        if not success:
            return Response({'status': 'failed to set'}, 500)

        await asyncio.sleep_ms(250)

        try:
            new_burner_data_obj = await npbc_controller.get_general_information()
            if new_burner_data_obj:
                new_burner_data_dict = new_burner_data_obj.to_dict()
                app_state['burner'] = new_burner_data_dict
                formatted_data = format_burner_data(new_burner_data_dict)
                return Response(json.dumps(formatted_data), 200)
            else:
                return Response({'status': 'failed to read back state'}, 500)
        except Exception as e:
            log(f"Error reading back state in /api/settings: {e}")
            return Response({'status': 'error readback'}, 500)

    return Response({'status': 'bad request'}, 400)

@app.route('/api/update', methods=['POST'])
async def api_update(request):
    log("OTA update requested.")
    try:
        success, message = ota_updater.download_and_install_update_if_available()
        return Response({'status': 'success' if success else 'no_update', 'message': message}, 200)
    except Exception as e:
        log(f"OTA update failed with exception: {e}")
        return Response({'status': 'error', 'message': str(e)}, 500)

@app.route('/api/reboot', methods=['POST'])
async def api_reboot(request):
    log("Reboot requested from web interface.")
    reset()

# --- Main Execution ---
sensor_reader = SensorReader()

async def main():
    global npbc_controller

    # Start FTP server if enabled (async, cooperates with event loop)
    if getattr(config, 'ENABLE_FTP', True):
        import uftpd
        uftpd.start()

    scheduler.load_schedules()

    npbc_controller = NPBCController(tx_pin=config.PIN_UART1_TX, rx_pin=config.PIN_UART1_RX)

    log("Starting data collector task...")
    asyncio.create_task(data_collector_task(npbc_controller, sensor_reader))

    log("Starting scheduler task...")
    asyncio.create_task(scheduler_task(npbc_controller, sensor_reader))

    log("Starting NTP sync task...")
    asyncio.create_task(ntp_sync_task())

    ip_addr = network.WLAN(network.STA_IF).ifconfig()[0]
    log(f'Starting web server on http://{ip_addr}')
    await app.start_server(port=80, debug=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
