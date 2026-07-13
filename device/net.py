"""Tiny network helpers: local IP + connectivity, for Piwi Connect and the
wifi status icon.
"""
import socket


def get_ip():
    """Best-guess LAN IP, or None if offline. Doesn't actually send anything."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))     # picks the interface with a default route
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def connected():
    return get_ip() is not None
