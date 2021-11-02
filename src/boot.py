# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)

import gc
import uos
import machine
import ntptime
import network
import webrepl

gc.collect()
machine.freq(240000000)  # set the CPU frequency to 240 MHz
webrepl.start()


# helper function to view file contents from commandline
def cat(Filename):
    f = open(Filename)
    print(f.read())
    f.close()


# ls
def ls():
    d = uos.listdir()
    return d


# Start wifi
def do_connect():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect('whitebox', 'nexus@home')
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())
do_connect()

# synchronize with ntp
ntptime.host = 'bg.pool.ntp.org'
ntptime.settime()  # set the rtc datetime from the remote server
