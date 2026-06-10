try:
    import network
except ImportError:
    network = None

import time


def wifi_supported():
    return network is not None


def connect_to_wifi(ssid, password, timeout_seconds=15):
    if network is None:
        raise RuntimeError("WiFi connection requires the MicroPython network module")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return wlan.ifconfig()[0]

    print("Connecting to WiFi...")
    wlan.connect(ssid, password)
    timeout = timeout_seconds

    while timeout > 0:
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print("Connected:", ip)
            return ip
        timeout -= 1
        time.sleep(1)
    raise RuntimeError("WiFi connection failed")


def connect_wifi(ssid, password):
    return connect_to_wifi(ssid, password)
