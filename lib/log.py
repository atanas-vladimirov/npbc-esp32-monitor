# lib/log.py - Timestamped logging for MicroPython
import gc
import time

_tz_func = None
_tz_posix = None

def setup(tz_func, tz_posix):
    """Configure timezone for log timestamps.
    Call once after imports: log.setup(tztime, config.TIMEZONE_POSIX)"""
    global _tz_func, _tz_posix
    _tz_func = tz_func
    _tz_posix = tz_posix

def log(msg):
    """Print a message prefixed with local date/time."""
    try:
        if _tz_func and _tz_posix:
            t = _tz_func(time.time(), _tz_posix)
        else:
            t = time.localtime()
        ts = f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    except Exception:
        ts = "----"
    print(f"[{ts}] [{gc.mem_free()}] {msg}")
