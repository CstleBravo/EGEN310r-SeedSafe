try:
    import time
except ImportError:
    time = None


class Clock:
    def now(self):
        if time is None:
            return (2026, 1, 1, 0, 0, 0, 0, 0)
        return time.localtime()

    def seconds(self):
        if time is None:
            return 0
        return time.time()

    def sleep(self, seconds):
        if time is not None:
            time.sleep(seconds)


class FakeMotor:
    def __init__(self):
        self.position = "closed"

    def open(self):
        print("Motor: opening feeder")
        self.position = "open"
        return True

    def close(self):
        print("Motor: closing feeder")
        self.position = "closed"
        return True


class FakePositionSensor:
    def __init__(self, motor):
        self.motor = motor

    def is_open(self):
        return self.motor.position == "open"

    def is_closed(self):
        return self.motor.position == "closed"


class StatusLight:
    def __init__(self):
        self.on_state = False

    def on(self):
        self.on_state = True
        print("Status light: on")

    def off(self):
        self.on_state = False
        print("Status light: off")
