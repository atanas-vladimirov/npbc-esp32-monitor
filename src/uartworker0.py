
import time
from machine import UART
import npbc_communication


def run():
  uart = UART(2)
  uart.init(baudrate=9600, tx=17, rx=16, bits=8, parity=None, stop=1, timeout=1000, rxbuf=256)

  try:

    time.sleep(0.1)
    requestData = npbc_communication.generalInformationCommand().getRequestData()
    uart.write(requestData)

    time.sleep(0.5)
    if uart.any():
      responseData = bytearray(uart.read())
    else:
      return({})

    if (len(responseData) > 0):
      response = npbc_communication.generalInformationCommand().processResponseData(responseData)

      if (isinstance(response, npbc_communication.generalInformationResponse)):

        if (response.FFWorkTime > 0):

          time.sleep(0.1)
          resetFFWorkTimeCounterCommandRequestData = npbc_communication.resetFFWorkTimeCounterCommand().getRequestData()
          uart.write(resetFFWorkTimeCounterCommandRequestData)

          time.sleep(0.5)
          if uart.any():
            resetFFWorkTimeCounterCommandResponseData = bytearray(uart.read())

          if (len(resetFFWorkTimeCounterCommandResponseData) > 0):
            resetFFWorkTimeCounterCommandResponse = npbc_communication.resetFFWorkTimeCounterCommand().processResponseData(resetFFWorkTimeCounterCommandResponseData)

            if (isinstance(resetFFWorkTimeCounterCommandResponse, npbc_communication.successResponse)):
              params = {'SwVer': response.SwVer, 'Date': response.Date, 'Mode': response.Mode, 'State': response.State, 'Status': response.Status, 'IgnitionFail': response.IgnitionFail, 'PelletJam': response.PelletJam, 'Tset': response.Tset, 'Tboiler': response.Tboiler, 'Flame': response.Flame,
                        'Heater': response.Heater, 'DHWPump': response.DHWPump, 'CHPump': response.CHPump, 'DHW': response.DHW, 'BF': response.BF, 'FF': response.FF, 'Fan': response.Fan, 'Power': response.Power, 'ThermostatStop': response.ThermostatStop, 'FFWorkTime': response.FFWorkTime}

        else:
          params = {'SwVer': response.SwVer, 'Date': response.Date, 'Mode': response.Mode, 'State': response.State, 'Status': response.Status, 'IgnitionFail': response.IgnitionFail, 'PelletJam': response.PelletJam, 'Tset': response.Tset, 'Tboiler': response.Tboiler, 'Flame': response.Flame,
                    'Heater': response.Heater, 'DHWPump': response.DHWPump, 'CHPump': response.CHPump, 'DHW': response.DHW, 'BF': response.BF, 'FF': response.FF, 'Fan': response.Fan, 'Power': response.Power, 'ThermostatStop': response.ThermostatStop, 'FFWorkTime': response.FFWorkTime}

        if (len(params) > 0):
          return(params)
        else:
          return({})

  except Exception as e1:
    return({"error communicating": str(e1)})
