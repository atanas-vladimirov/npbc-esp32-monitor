
import time
from machine import UART
import npbc_communication


class SerialProcessSet():
  def __init__(self, Mode, Priority):
    self.__Mode = Mode
    self.__Priority = Priority
		
  def run(self):
    uart = UART(2)
    uart.init(baudrate=9600, tx=17, rx=16, bits=8, parity=None, stop=1, timeout=1000, rxbuf=256)

    try:  
  
      time.sleep(0.1)
      requestData = npbc_communication.setModeAndPriorityCommand(self.__Mode,self.__Priority).getRequestData()
      uart.write(requestData)

      time.sleep(0.5)
      if uart.any():
        responseData = bytearray(uart.read())
      else:
        return({})                

      if (len(responseData) > 0):
        response = npbc_communication.setModeAndPriorityCommand(self.__Mode,self.__Priority).processResponseData(responseData)

    except Exception as e1:
      return({"error communicating": str(e1)})