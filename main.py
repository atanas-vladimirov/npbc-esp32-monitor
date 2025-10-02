# main.py
import gc
import json
import uasyncio as asyncio
import urequests as requests
from machine import Pin, SPI, reset
import network
import time

# Web framework
from microdot import Microdot, Response, send_file

# App-specific imports
import config
from lib.npbc import NPBCController
from lib.ota import OTAUpdater
from lib.scheduler import Scheduler
from drivers.max6675 import MAX6675
from drivers.bme280_driver import BME280
import onewire
import ds18x20
import math

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
                  sck=Pin(config.PIN_SPI_SCK), 
                  miso=Pin(config.PIN_SPI_MISO))

        spi2 = SPI(2, baudrate=100000,
                  sck=Pin(config.PIN_BME_SCK), 
                  mosi=Pin(config.PIN_BME_MOSI), 
                  miso=Pin(config.PIN_BME_MISO))

        try:
            # Try to initialize the BME/BMP sensor
            bme_cs = Pin(config.PIN_BME_CS)
            self.bme = BME280(spi=spi2, cs=bme_cs)
            print(f"Detected Chip ID: {hex(self.bme.chip_id)}. Is BME280: {self.bme.is_bme280}")
        except OSError as e:
            # If it fails (e.g., not connected), set the object to None
            print(f"BME/BMP sensor not found. Continuing without it. Error: {e}")
            self.bme = None

        # The rest of the sensors initialize as normal
        self.k_type = MAX6675(spi=spi1, cs_pin=config.PIN_MAX6675_CS)

        ds_pin = Pin(config.PIN_DS18X20)
        self.ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))
        roms = self.ds_sensor.scan()
        self.ds_rom = roms[0] if roms else None

    async def read_all(self):
        data = {}

        # --- Check if the sensor exists before reading ---
        if self.bme:
            # Sensor was found, so read from it
            data['BME_TYPE'] = 'BME280' if self.bme.is_bme280 else 'BMP280'
            try:
                temp, press, hum = self.bme.values
                data['TBMP'] = round(temp, 2)
                data['PBMP'] = round(press, 2)
                if hum is not None:
                    data['HUM'] = round(hum, 2)
            except Exception as e:
                print(f"Error reading BME/BMP sensor: {e}")
                # Provide default values on read error
                data['TBMP'], data['PBMP'] = 0, 0
        else:
            # Sensor was not found during init, provide default values
            data['BME_TYPE'] = 'N/A'
            data['TBMP'] = 0
            data['PBMP'] = 0
            # 'HUM' will be absent, and the frontend will handle it

        # Read other sensors as normal
        if self.ds_rom:
            self.ds_sensor.convert_temp()
            await asyncio.sleep_ms(750)
            data['TDS18'] = round(self.ds_sensor.read_temp(self.ds_rom), 2)
        else:
            data['TDS18'] = 0

        # Handle NaN from K-Type sensor
        k_type_temp = self.k_type.read()
        if k_type_temp is not None and math.isnan(k_type_temp):
            # Use 0.0 instead of None to satisfy the NOT NULL database constraint
            data['KTYPE'] = 0.0
            print("Warning: K-Type sensor returned NaN (check wiring). Defaulting to 0.0.")
        else:
            data['KTYPE'] = k_type_temp

        return data

# --- Main Application Tasks ---
async def data_collector_task(npbc, sensors):
    while True:
        print("Collecting data...")
        try:
            # Get the response object from the controller
            burner_response_object = await npbc.get_general_information()
            sensor_data = await sensors.read_all()

            # Convert the object to a dictionary if it's not None
            burner_data = {}
            if burner_response_object:
                burner_data = burner_response_object.to_dict()

            # Only proceed if we have valid data from the burner
            if not burner_data:
                print("Failed to get burner data, skipping post for this cycle.")
                # Wait for the next cycle without posting
                await asyncio.sleep(30)
                continue

            # Get the offset from config, defaulting to 0 if not found
            offset_hours = getattr(config, 'TIMEZONE_OFFSET', 0)
            local_timestamp = time.time() + (offset_hours * 3600)
            local_time_tuple = time.localtime(local_timestamp)

            # Update global state with the new dictionary
            app_state['burner'] = burner_data
            app_state['sensors'] = sensor_data
            app_state['last_update'] = f"{local_time_tuple[3]:02d}:{local_time_tuple[4]:02d}:{local_time_tuple[5]:02d}"

            # The rest of the logic now works with the 'burner_data' dictionary
            full_data = burner_data.copy()
            full_data.update(sensor_data)

            try:
                # 1. Add the debug print you requested
                print("--- Sending Data to Server ---")
                print(full_data)

                # 2. Make the request and get the response object
                response = requests.post(
                    config.REMOTE_POST_URL,
                    json=full_data,
                    headers={'content-type': 'application/json'}
                )

                # 3. Check the server's response status code
                if response.status_code == 200:
                    print("Data posted successfully (Server responded OK).")
                else:
                    print(f"Error: Server responded with status {response.status_code}")
                    print(f"Response body: {response.text}")

                response.close() # Always close the response

            except Exception as e:
                print(f"Host unreachable or request failed: {e}")

        except Exception as e:
            print(f"Error in data collection: {e}")

        gc.collect()
        await asyncio.sleep(30)

# --- Scheduler Task ---
async def scheduler_task(npbc, sensor_reader):
    """
    Runs every minute to check and execute schedules.
    """
    while True:
        try:
            current_time = time.localtime()
            current_hour = current_time[3]
            current_minute = current_time[4]
            # tm_wday: Monday is 0 and Sunday is 6
            current_day_of_week = current_time[6]

            current_temp = app_state.get('sensors', {}).get('TBMP', 999)

            schedules = scheduler.get_schedules()

            for sched in schedules:
                if not sched.get('enabled', False):
                    continue

                # Check if today is a scheduled day
                if not sched['days'][current_day_of_week]:
                    continue

                # --- Check for ON time ---
                on_hour, on_minute = map(int, sched['on_time'].split(':'))
                if on_hour == current_hour and on_minute == current_minute:
                    print(f"Scheduler: Matched ON time for '{sched['name']}'")

                    # Check temperature condition
                    temp_ok = False
                    condition = sched.get('temp_condition', 'none')
                    threshold = sched.get('temp_threshold', 0)

                    if condition == 'none':
                        temp_ok = True
                    elif condition == 'below' and current_temp < threshold:
                        temp_ok = True
                        print(f"Temp condition met: {current_temp}°C is below {threshold}°C")
                    elif condition == 'above' and current_temp > threshold:
                        temp_ok = True
                        print(f"Temp condition met: {current_temp}°C is above {threshold}°C")

                    if temp_ok:
                        print(f"Executing ON action for '{sched['name']}'")
                        # Set Mode to Auto (1) with the specified priority
                        await npbc.set_mode_and_priority(1, sched['priority_on'])
                    else:
                        print(f"Temp condition NOT met for '{sched['name']}'. Skipping.")

                # --- Check for OFF time ---
                off_hour, off_minute = map(int, sched['off_time'].split(':'))
                if off_hour == current_hour and off_minute == current_minute:
                    print(f"Scheduler: Matched OFF time for '{sched['name']}'. Executing OFF action.")
                    # Set Mode to Standby (0)
                    await npbc.set_mode_and_priority(0, 0)

        except Exception as e:
            print(f"Error in scheduler task: {e}")

        # Wait 60 seconds before the next check
        await asyncio.sleep(60)

# --- ASYNC WRAPPER FOR BOOT-TIME UPDATE ---
async def boot_time_update_check():
    """
    Waits for network to be ready, then checks for OTA updates.
    This is a proper coroutine that can be scheduled.
    """
    # Wait 10 seconds to ensure WiFi is fully connected and stable
    await asyncio.sleep(10)

    print("Checking for updates on boot...")
    try:
        # Now we call the synchronous update function.
        # This will block the event loop temporarily, but only after the
        # web server and other tasks have already started.
        ota_updater.download_and_install_update_if_available()
    except Exception as e:
        print(f"Boot-time update check failed: {e}")

# --- Web Server Setup ---
app = Microdot()
Response.default_content_type = 'text/html'

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

@app.route('/')
async def index(request):
    return send_file('templates/index.html')

@app.route('/static/<path:path>')
def static(request, path):
    return send_file(f'static/{path}')

@app.route('/api/data')
async def api_data(request):
    full_state = {
        'burner': format_burner_data(app_state.get('burner', {})),
        'sensors': app_state.get('sensors', {}),
        'last_update': app_state.get('last_update')
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
    data = request.json
    mode, priority = data.get('mode'), data.get('priority')
    if mode is not None and priority is not None:
        success = await npbc_controller.set_mode_and_priority(int(mode), int(priority))
        return Response({'status': 'ok' if success else 'failed'}, 200 if success else 500)
    return Response({'status': 'bad request'}, 400)

@app.route('/api/update', methods=['POST'])
async def api_update(request):
    print("OTA update requested.")
    try:
        success, message = ota_updater.download_and_install_update_if_available()
        return Response({'status': 'success' if success else 'no_update', 'message': message}, 200)
    except Exception as e:
        print(f"OTA update failed with exception: {e}")
        return Response({'status': 'error', 'message': str(e)}, 500)

# --- REBOOT ENDPOINT ---
@app.route('/api/reboot', methods=['POST'])
async def api_reboot(request):
    print("Reboot requested from web interface.")
    # This will not return a response, the client will see a connection error
    reset()

# --- Main Execution ---
npbc_controller = NPBCController(tx_pin=config.PIN_UART2_TX, rx_pin=config.PIN_UART2_RX)
sensor_reader = SensorReader()

async def main():
    # Load schedules from flash memory at startup
    scheduler.load_schedules()

    #print("Checking for updates on boot...")
    #asyncio.create_task(boot_time_update_check())

    print("Starting data collector task...")
    asyncio.create_task(data_collector_task(npbc_controller, sensor_reader))

    print("Starting scheduler task...")
    asyncio.create_task(scheduler_task(npbc_controller, sensor_reader))

    ip_addr = network.WLAN(network.STA_IF).ifconfig()[0]
    print(f'Starting web server on http://{ip_addr}')
    await app.run(port=80, debug=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
