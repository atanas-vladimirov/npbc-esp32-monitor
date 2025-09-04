# uftpd.py
# (Content of the uftpd.py file you provided goes here)
#
# Small ftp server for ESP8266 Micropython
# Based on the work of chrisgp - Christopher Popp and pfalcon - Paul Sokolovsky
#
# The server accepts passive mode only. It runs in background.
# Start the server with:
#
# import uftpd
#
# Copyright (c) 2016 Christopher Popp (initial ftp server framework)
# Copyright (c) 2016 Paul Sokolovsky (background execution control structure)
# Copyright (c) 2016 Robert Hammelrath (putting the pieces together and a
# few extensions)
# Copyright (c) 2020 Jan Wieck Use separate FTP servers per socket for STA + AP mode
# Copyright (c) 2021 JD Smith Use a preallocated buffer and improve error handling.
# Distributed under MIT License
#
import socket
import network
import uos
import gc
import sys
import errno
from time import sleep_ms, localtime
from micropython import alloc_emergency_exception_buf

_CHUNK_SIZE = const(1024)
_SO_REGISTER_HANDLER = const(20)
_COMMAND_TIMEOUT = const(300)
_DATA_TIMEOUT = const(100)
_DATA_PORT = const(13333)

ftpsockets = []
datasocket = None
client_list = []
verbose_l = 0
client_busy = False

_month_name = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

class FTP_client:
    def __init__(self, ftpsocket, local_addr):
        self.command_client, self.remote_addr = ftpsocket.accept()
        self.remote_addr = self.remote_addr[0]
        self.command_client.settimeout(_COMMAND_TIMEOUT)
        log_msg(1, "FTP Command connection from:", self.remote_addr)
        self.command_client.setsockopt(socket.SOL_SOCKET, _SO_REGISTER_HANDLER, self.exec_ftp_command)
        self.command_client.sendall("220 Hello, this is the {}.\r\n".format(sys.platform))
        self.cwd, self.fromname, self.active = '/', None, True
        self.pasv_data_addr, self.DATA_PORT = local_addr, 20
        self.act_data_addr = self.remote_addr

    def send_list_data(self, path, data_client, full):
        try:
            for fname in uos.listdir(path):
                data_client.sendall(self.make_description(path, fname, full))
        except Exception:
            path, pattern = self.split_path(path)
            try:
                for fname in uos.listdir(path):
                    if self.fncmp(fname, pattern):
                        data_client.sendall(self.make_description(path, fname, full))
            except Exception: pass

    def make_description(self, path, fname, full):
        if full:
            stat = uos.stat(self.get_absolute_path(path, fname))
            file_permissions = "drwxr-xr-x" if (stat[0] & 0o170000 == 0o040000) else "-rw-r--r--"
            file_size = stat[6]
            tm = localtime(stat[7])
            if tm[0] != localtime()[0]:
                description = "{} 1 owner group {:>10} {} {:2} {:>5} {}\r\n".format(file_permissions, file_size, _month_name[tm[1]], tm[2], tm[0], fname)
            else:
                description = "{} 1 owner group {:>10} {} {:2} {:02}:{:02} {}\r\n".format(file_permissions, file_size, _month_name[tm[1]], tm[2], tm[3], tm[4], fname)
        else:
            description = fname + "\r\n"
        return description

    def send_file_data(self, path, data_client):
        buffer = bytearray(_CHUNK_SIZE)
        mv = memoryview(buffer)
        with open(path, "rb") as file:
            bytes_read = file.readinto(buffer)
            while bytes_read > 0:
                data_client.write(mv[0:bytes_read])
                bytes_read = file.readinto(buffer)
        data_client.close()

    def save_file_data(self, path, data_client, mode):
        buffer = bytearray(_CHUNK_SIZE)
        mv = memoryview(buffer)
        with open(path, mode) as file:
            bytes_read = data_client.readinto(buffer)
            while bytes_read > 0:
                file.write(mv[0:bytes_read])
                bytes_read = data_client.readinto(buffer)
        data_client.close()

    def get_absolute_path(self, cwd, payload):
        if payload.startswith('/'): cwd = "/"
        for token in payload.split("/"):
            if token == '..':
                cwd = self.split_path(cwd)[0]
            elif token != '.' and token != '':
                cwd = cwd + '/' + token if cwd != '/' else '/' + token
        return cwd

    def split_path(self, path):
        tail = path.split('/')[-1]
        head = path[:-(len(tail) + 1)]
        return ('/' if head == '' else head, tail)

    def fncmp(self, fname, pattern):
        pi, si = 0, 0
        while pi < len(pattern) and si < len(fname):
            if (fname[si] == pattern[pi]) or (pattern[pi] == '?'):
                si, pi = si + 1, pi + 1
            else:
                if pattern[pi] == '*':
                    if pi == len(pattern.rstrip("*?")): return True
                    while si < len(fname):
                        if self.fncmp(fname[si:], pattern[pi + 1:]): return True
                        else: si += 1
                    return False
                else: return False
        return pi == len(pattern.rstrip("*")) and si == len(fname)

    def open_dataclient(self):
        if self.active:
            data_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_client.settimeout(_DATA_TIMEOUT)
            data_client.connect((self.act_data_addr, self.DATA_PORT))
            log_msg(1, "FTP Data connection with:", self.act_data_addr)
        else:
            data_client, data_addr = datasocket.accept()
            log_msg(1, "FTP Data connection with:", data_addr[0])
        return data_client

    def exec_ftp_command(self, cl):
        global datasocket, client_busy
        try:
            gc.collect()
            data = cl.readline().decode("utf-8").rstrip("\r\n")
            if not data:
                log_msg(1, "*** No data, assume QUIT"); close_client(cl)
                return
            if client_busy: cl.sendall("400 Device busy.\r\n"); return
            client_busy = True
            command = data.split()[0].upper()
            payload = data[len(command):].lstrip()
            path = self.get_absolute_path(self.cwd, payload)
            log_msg(1, "Command={}, Payload={}".format(command, payload))
            
            # Simplified command handling
            if command == "USER": cl.sendall("230 Logged in.\r\n")
            elif command == "PASS": cl.sendall("230 Logged in.\r\n")
            elif command == "SYST": cl.sendall("215 UNIX Type: L8\r\n")
            elif command in ("TYPE", "NOOP", "ABOR"): cl.sendall('200 OK\r\n')
            elif command == "QUIT": cl.sendall('221 Bye.\r\n'); close_client(cl)
            elif command in ("PWD", "XPWD"): cl.sendall('257 "{}"\r\n'.format(self.cwd))
            elif command in ("CWD", "XCWD"):
                try:
                    if (uos.stat(path)[0] & 0o170000) == 0o040000: self.cwd = path; cl.sendall('250 OK\r\n')
                    else: cl.sendall('550 Fail\r\n')
                except: cl.sendall('550 Fail\r\n')
            elif command == "PASV":
                cl.sendall('227 Entering Passive Mode ({},{},{}).\r\n'.format(self.pasv_data_addr.replace('.', ','), _DATA_PORT >> 8, _DATA_PORT % 256))
                self.active = False
            elif command == "PORT":
                items = payload.split(",");
                if len(items) >= 6:
                    self.act_data_addr = '.'.join(items[:4])
                    if self.act_data_addr == "127.0.1.1": self.act_data_addr = self.remote_addr
                    self.DATA_PORT = int(items[4]) * 256 + int(items[5])
                    cl.sendall('200 OK\r\n'); self.active = True
                else: cl.sendall('504 Fail\r\n')
            elif command in ("LIST", "NLST"):
                option = payload.split()[0].lower() if payload.startswith("-") else ""
                path = self.get_absolute_path(self.cwd, payload[len(option):].lstrip()) if option else path
                try:
                    data_client = self.open_dataclient()
                    cl.sendall("150 Directory listing:\r\n")
                    self.send_list_data(path, data_client, command == "LIST" or 'l' in option)
                    data_client.close(); cl.sendall("226 Done.\r\n")
                except: cl.sendall('550 Fail\r\n')
            elif command in ("RETR", "STOR", "APPE"):
                try:
                    data_client = self.open_dataclient()
                    cl.sendall("150 Opened data connection.\r\n")
                    if command == "RETR": self.send_file_data(path, data_client)
                    else: self.save_file_data(path, data_client, "wb" if command == "STOR" else "ab")
                    cl.sendall("226 Done.\r\n")
                except Exception as e: log_msg(1, e); cl.sendall('550 Fail\r\n')
            elif command == "SIZE":
                try: cl.sendall('213 {}\r\n'.format(uos.stat(path)[6]))
                except: cl.sendall('550 Fail\r\n')
            elif command == "MDTM":
                try: cl.sendall('213 {:04d}{:02d}{:02d}{:02d}{:02d}{:02d}\r\n'.format(*localtime(uos.stat(path)[8])[0:6]))
                except: cl.sendall('550 Fail\r\n')
            elif command == "DELE":
                try: uos.remove(path); cl.sendall('250 OK\r\n')
                except: cl.sendall('550 Fail\r\n')
            elif command == "RNFR":
                try: uos.stat(path); self.fromname = path; cl.sendall("350 Rename from\r\n")
                except: cl.sendall('550 Fail\r\n')
            elif command == "RNTO":
                try: uos.rename(self.fromname, path); cl.sendall('250 OK\r\n')
                except: cl.sendall('550 Fail\r\n')
                self.fromname = None
            elif command in ("CDUP", "XCUP"): self.cwd = self.get_absolute_path(self.cwd, ".."); cl.sendall('250 OK\r\n')
            elif command in ("RMD", "XRMD", "MKD", "XMKD"):
                try:
                    if 'M' in command: uos.mkdir(path) if 'K' in command else uos.rmdir(path)
                    cl.sendall('250 OK\r\n')
                except: cl.sendall('550 Fail\r\n')
            else: cl.sendall("502 Unsupported command.\r\n")
        except OSError as err:
            if err.errno in (errno.ECONNABORTED, errno.ENOTCONN): close_client(cl)
        except Exception as err: log_msg(1, "Exception in exec_ftp_command: {}".format(err))
        client_busy = False

def log_msg(level, *args):
    if verbose_l >= level: print(*args)

def close_client(cl):
    cl.setsockopt(socket.SOL_SOCKET, _SO_REGISTER_HANDLER, None)
    cl.close()
    for i, client in enumerate(client_list):
        if client.command_client == cl: del client_list[i]; break

def accept_ftp_connect(ftpsocket, local_addr):
    try: client_list.append(FTP_client(ftpsocket, local_addr))
    except:
        try:
            temp_client, _ = ftpsocket.accept(); temp_client.close()
        except: pass

def start(port=21, verbose=0, splash=True):
    global ftpsockets, datasocket, verbose_l, client_list, client_busy
    alloc_emergency_exception_buf(100); verbose_l, client_list, client_busy = verbose, [], False
    for interface in [network.AP_IF, network.STA_IF]:
        wlan = network.WLAN(interface)
        if wlan.active():
            ifconfig = wlan.ifconfig()
            addr = socket.getaddrinfo(ifconfig[0], port)[0][-1]
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(addr); sock.listen(1)
            sock.setsockopt(socket.SOL_SOCKET, _SO_REGISTER_HANDLER, lambda s : accept_ftp_connect(s, ifconfig[0]))
            ftpsockets.append(sock)
            if splash: print("FTP server started on {}:{}".format(ifconfig[0], port))
    datasocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    datasocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    datasocket.bind(('0.0.0.0', _DATA_PORT)); datasocket.listen(1); datasocket.settimeout(10)

start(splash=False)
