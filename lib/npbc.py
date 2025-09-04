# lib/npbc.py
import time
from machine import UART
import uasyncio as asyncio

class CommandBase:
    _HEADER = bytearray([0x5A, 0x5A])

    def __init__(self, command_id):
        self._command_id = command_id
        self.is_successful = False

    def _calculate_checksum(self, data):
        return (sum(data) & 0xFF) ^ 0xFF

    def get_request(self, data=bytearray()):
        request = bytearray()
        request.append(len(data) + 2)
        request.append(self._command_id)
        request.extend(data)
        request.append(self._calculate_checksum(request))

        for i in range(2, len(request)):
            request[i] = (request[i] + i - 1) & 0xFF

        return self._HEADER + request

    def process_response(self, data):
        self.is_successful = False
        if len(data) < 5 or not data.startswith(self._HEADER):
            print("Invalid response header")
            return None

        if len(data) != len(self._HEADER) + 1 + data[2]:
            print("Invalid response length")
            return None

        response_payload = bytearray(data[3:-1])

        for i in range(1, len(response_payload)):
            response_payload[i] = (response_payload[i] - i + 1) & 0xFF

        calculated_checksum = (self._calculate_checksum(response_payload) + len(response_payload) - 1) & 0xFF
        if data[-1] != calculated_checksum:
            print("Response checksum failed")
            return None

        self.is_successful = True
        return response_payload[1:]

class GeneralInfoCmd(CommandBase):
    def __init__(self):
        super().__init__(0x01)

class ResetFFWorkTimeCmd(CommandBase):
    def __init__(self):
        super().__init__(0x09)

class SetModeAndPriorityCmd(CommandBase):
    def __init__(self, mode, priority):
        super().__init__(0x03)
        self.mode = mode
        self.priority = priority
    def get_request(self):
        return super().get_request(bytearray([self.mode, self.priority]))

class NPBCController:
    """A controller for the Naturela Pellet Burner Controller via UART."""
    def __init__(self, tx_pin, rx_pin, baudrate=9600):
        self.uart = UART(2, baudrate=baudrate, tx=tx_pin, rx=rx_pin, timeout=1000, rxbuf=256)
        self.lock = asyncio.Lock()

    async def _send_command(self, cmd_instance):
        async with self.lock:
            try:
                request = cmd_instance.get_request()
                self.uart.write(request)
                await asyncio.sleep_ms(500)

                if self.uart.any():
                    response_data = self.uart.read()
                    return cmd_instance.process_response(response_data)
                else:
                    print(f"No response for command {cmd_instance._command_id}")
                    return None
            except Exception as e:
                print(f"Error sending command: {e}")
                return None

    def _parse_info_response(self, data):
        if data is None or len(data) < 28:
            return None
        return {
            'SwVer': f'{(data[1] >> 4)}.{ (data[1] & 0x0F)}',
            'Date': f'{2000 + data[7]:04d}-{data[6]:02d}-{data[5]:02d} {data[2]:02d}:{data[3]:02d}:{data[4]:02d}',
            'Mode': data[8], 'State': data[9], 'Status': data[10],
            'IgnitionFail': (data[13] & 0x01) != 0, 'PelletJam': (data[13] & 0x20) != 0,
            'Tset': data[16], 'Tboiler': data[17], 'DHW': data[18], 'Flame': data[20],
            'Heater': (data[21] & 0x02) != 0, 'DHWPump': (data[21] & 0x04) != 0,
            'CHPump': (data[21] & 0x08) != 0, 'BF': (data[21] & 0x10) != 0,
            'FF': (data[21] & 0x20) != 0, 'Fan': data[23], 'Power': data[24],
            'ThermostatStop': (data[25] & 0x80) != 0, 'FFWorkTime': data[27]
        }

    async def get_general_information(self):
        cmd = GeneralInfoCmd()
        raw_response = await self._send_command(cmd)

        if not cmd.is_successful:
            return {'error': 'Failed to get general information'}

        info = self._parse_info_response(raw_response)

        if info and info['FFWorkTime'] > 0:
            reset_cmd = ResetFFWorkTimeCmd()
            await self._send_command(reset_cmd)
            if not reset_cmd.is_successful:
                print("Failed to reset FFWorkTime counter.")

        return info

    async def set_mode_and_priority(self, mode, priority):
        cmd = SetModeAndPriorityCmd(mode, priority)
        await self._send_command(cmd)
        return cmd.is_successful
