# lib/npbc.py
import time
from machine import UART
import uasyncio as asyncio
import sys

class CommandBase:
    _HEADER = b'\x5a\x5a'

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
        full_request = self._HEADER + request
        return full_request

    def process_response(self, data):
        self.is_successful = False
        if len(data) < 5 or not data.startswith(self._HEADER):
            print("Invalid response header")
            return None

        if len(data) != len(self._HEADER) + 1 + data[2]:
            print("Invalid response length")
            return None

        # The slice must start at index 2 to include the length byte, not 3.
        response_payload = bytearray(data[2:-1])

        for i in range(1, len(response_payload)):
            response_payload[i] = (response_payload[i] - i + 1) & 0xFF

        calculated_checksum = (self._calculate_checksum(response_payload) + len(response_payload) - 1) & 0xFF
        if data[-1] != calculated_checksum:
            print("Response checksum validation failed")
            return None

        self.is_successful = True
        return response_payload[1:]

class GeneralInfoCmd(CommandBase):
  def __init__(self):
    super().__init__(0x01)
  def get_request(self):
    return super().get_request()
  def process_response(self, response):
    responseData = super().process_response(response)
    if self.is_successful:
      class generalInformationResponse:
        def __init__(self, data):
            # A helper function to decode one BCD byte into a decimal number.
            def bcd_to_dec(bcd_byte):
                return (bcd_byte >> 4) * 10 + (bcd_byte & 0x0F)

            # ... (all the self.SwVer, self.Mode, etc. initializations remain the same)
            self.SwVer = f'{(data[1] >> 4)}.{ (data[1] & 0x0F)}'
            # --- CORRECTED DATE/TIME LOGIC ---
            year = 2000 + bcd_to_dec(data[7])
            month = bcd_to_dec(data[6])
            day = bcd_to_dec(data[5])
            hour = bcd_to_dec(data[2])
            minute = bcd_to_dec(data[3])
            second = bcd_to_dec(data[4])
            self.Date = f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}'
            # --- END OF FIX ---
            self.Mode = data[8]
            self.State = data[9]
            self.Status = data[10]
            self.IgnitionFail = (data[13] & 0x01) != 0
            self.PelletJam = (data[13] & 0x20) != 0
            self.Tset = data[16]
            self.Tboiler = data[17]
            self.DHW = data[18]
            self.Flame = data[20]
            self.Heater = (data[21] & 0x02) != 0
            self.DHWPump = (data[21] & 0x04) != 0
            self.CHPump = (data[21] & 0x08) != 0
            self.BF = (data[21] & 0x10) != 0
            self.FF = (data[21] & 0x20) != 0
            self.Fan = data[23]
            self.Power = data[24]
            self.ThermostatStop = (data[25] & 0x80) != 0
            self.FFWorkTime = data[27]

        def to_dict(self):
          """Converts the response object to a dictionary."""
          return {key: value for key, value in self.__dict__.items()}

      return generalInformationResponse(responseData)
    else:
      return None

class ResetFFWorkTimeCmd(CommandBase):
  def __init__(self):
    super().__init__(0x09)
  def get_request(self):
    return super().get_request()

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
                print("--- CAUGHT AN EXCEPTION ---")
                sys.print_exception(e)
                return None

    def _parse_info_response(self, data):
        # This function is no longer needed as parsing is in GeneralInfoCmd
        return data # Simply return the parsed object

    async def get_general_information(self):
        cmd = GeneralInfoCmd()
        info = await self._send_command(cmd)

        if info and info.FFWorkTime > 0:
            reset_cmd = ResetFFWorkTimeCmd()
            await self._send_command(reset_cmd)
            # We don't need to check the response of the reset command for now

        return info

    async def set_mode_and_priority(self, mode, priority):
        cmd = SetModeAndPriorityCmd(mode, priority)
        await self._send_command(cmd)
        return cmd.is_successful