import time


def utcnow_z():
    """UTC, Z-suffixed, second precision. Never use %z: it emits a colon-free
    local offset that 3.6 cannot parse back and that sorts wrongly."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
