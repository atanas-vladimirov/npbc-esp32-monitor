# uftpd.py — Minimal async FTP server for MicroPython
# Stripped to bare essentials to minimize RAM usage.
# Supports: PASV, LIST, STOR, RETR, CWD, MKD, RMD, DELE, QUIT

import socket
import uos
import gc
import uasyncio as asyncio
import network

_DP = const(13333)
_running = False
_task = None
_ip = ''


def _p(cwd, arg):
    if arg.startswith('/'):
        cwd = '/'
    for t in arg.split('/'):
        if t == '..':
            cwd = cwd.rsplit('/', 1)[0] or '/'
        elif t and t != '.':
            cwd = cwd + ('/' if cwd != '/' else '') + t
    return cwd


async def _sess(s, ip):
    cwd = '/'
    ds = None
    try:
        s.sendall(b"220 OK\r\n")
        while _running:
            await asyncio.sleep_ms(20)
            s.settimeout(0.1)
            try:
                r = s.readline()
            except OSError:
                continue
            if not r:
                break
            l = r.decode().strip()
            if not l:
                continue
            pp = l.split(None, 1)
            c = pp[0].upper()
            a = pp[1] if len(pp) > 1 else ''
            pa = _p(cwd, a)
            gc.collect()
            try:
                if c in ("USER", "PASS"):
                    s.sendall(b"230 OK\r\n")
                elif c == "SYST":
                    s.sendall(b"215 UNIX Type: L8\r\n")
                elif c in ("TYPE", "NOOP", "ABOR", "FEAT"):
                    s.sendall(b"200 OK\r\n")
                elif c == "QUIT":
                    s.sendall(b"221 Bye\r\n")
                    break
                elif c in ("PWD", "XPWD"):
                    s.sendall('257 "{}"\r\n'.format(cwd).encode())
                elif c in ("CWD", "XCWD"):
                    try:
                        if uos.stat(pa)[0] & 0x4000:
                            cwd = pa
                            s.sendall(b"250 OK\r\n")
                        else:
                            s.sendall(b"550 Fail\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                elif c in ("CDUP", "XCUP"):
                    cwd = _p(cwd, "..")
                    s.sendall(b"250 OK\r\n")
                elif c == "PASV":
                    if ds:
                        try:
                            ds.close()
                        except Exception:
                            pass
                    ds = socket.socket()
                    ds.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    ds.bind(('0.0.0.0', _DP))
                    ds.listen(1)
                    ds.settimeout(10)
                    s.sendall("227 ({},{},{})\r\n".format(
                        ip.replace('.', ','), _DP >> 8, _DP & 255).encode())
                elif c in ("LIST", "NLST"):
                    lp = cwd if (not a or a.startswith('-')) else pa
                    try:
                        dc, _ = ds.accept()
                        s.sendall(b"150 OK\r\n")
                        for f in uos.listdir(lp):
                            st = uos.stat(lp + ('/' if lp != '/' else '') + f)
                            d = 'd' if st[0] & 0x4000 else '-'
                            dc.sendall("{}rw-r--r-- 1 0 0 {:>10} Jan  1 00:00 {}\r\n".format(
                                d, st[6], f).encode())
                        dc.close()
                        s.sendall(b"226 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                    if ds:
                        try:
                            ds.close()
                        except Exception:
                            pass
                        ds = None
                elif c == "RETR":
                    try:
                        dc, _ = ds.accept()
                        s.sendall(b"150 OK\r\n")
                        buf = bytearray(1024)
                        mv = memoryview(buf)
                        with open(pa, "rb") as f:
                            n = f.readinto(buf)
                            while n > 0:
                                dc.write(mv[:n])
                                n = f.readinto(buf)
                                await asyncio.sleep_ms(0)
                        dc.close()
                        s.sendall(b"226 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                    if ds:
                        try:
                            ds.close()
                        except Exception:
                            pass
                        ds = None
                elif c in ("STOR", "APPE"):
                    try:
                        dc, _ = ds.accept()
                        s.sendall(b"150 OK\r\n")
                        buf = bytearray(1024)
                        mv = memoryview(buf)
                        with open(pa, "wb" if c == "STOR" else "ab") as f:
                            n = dc.readinto(buf)
                            while n > 0:
                                f.write(mv[:n])
                                n = dc.readinto(buf)
                                await asyncio.sleep_ms(0)
                        dc.close()
                        s.sendall(b"226 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                    if ds:
                        try:
                            ds.close()
                        except Exception:
                            pass
                        ds = None
                elif c == "SIZE":
                    try:
                        s.sendall("213 {}\r\n".format(uos.stat(pa)[6]).encode())
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                elif c == "DELE":
                    try:
                        uos.remove(pa)
                        s.sendall(b"250 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                elif c in ("MKD", "XMKD"):
                    try:
                        uos.mkdir(pa)
                        s.sendall(b"257 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                elif c in ("RMD", "XRMD"):
                    try:
                        uos.rmdir(pa)
                        s.sendall(b"250 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                elif c == "RNFR":
                    try:
                        uos.stat(pa)
                        _rnfr = pa
                        s.sendall(b"350 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                elif c == "RNTO":
                    try:
                        uos.rename(_rnfr, pa)
                        s.sendall(b"250 OK\r\n")
                    except Exception:
                        s.sendall(b"550 Fail\r\n")
                else:
                    s.sendall(b"502 Unsupported\r\n")
            except OSError:
                break
            except Exception:
                pass
    finally:
        if ds:
            try:
                ds.close()
            except Exception:
                pass


async def _run(port):
    global _running
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', port))
    srv.listen(1)
    srv.settimeout(0.5)
    try:
        while _running:
            try:
                c, a = srv.accept()
            except OSError:
                await asyncio.sleep_ms(100)
                continue
            c.settimeout(300)
            try:
                await _sess(c, _ip)
            except Exception:
                pass
            try:
                c.close()
            except Exception:
                pass
            gc.collect()
    except asyncio.CancelledError:
        pass
    finally:
        srv.close()


def start(port=21):
    global _running, _task, _ip
    if _running:
        return
    gc.collect()
    _ip = network.WLAN(network.STA_IF).ifconfig()[0]
    _running = True
    _task = asyncio.create_task(_run(port))
    print("FTP server started on {}:{}".format(_ip, port))


def stop():
    global _running, _task
    _running = False
    if _task:
        try:
            _task.cancel()
        except Exception:
            pass
        _task = None
    gc.collect()
