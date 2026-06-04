try:
    import time
except ImportError:
    time = None

try:
    from machine import Pin
except ImportError:
    Pin = None


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
    def __init__(self, pin_id=None):
        self.on_state = False
        self.pin = None

        if Pin is not None and pin_id is not None:
            self.pin = Pin(pin_id, Pin.OUT)

    def on(self):
        self.on_state = True
        if self.pin is not None:
            self.pin.value(1)
        else:
            print("Status light: on")

    def off(self):
        self.on_state = False
        if self.pin is not None:
            self.pin.value(0)
        else:
            print("Status light: off")


class PicoDigitalMotor:
    """Basic two-pin motor control placeholder for the Pico.

    This assumes a motor driver where one pin requests open direction and one
    pin requests close direction. If the final design uses a servo, stepper, or
    H-bridge with PWM speed control, this class should be changed to match that
    driver instead of changing the controller logic.
    """

    def __init__(self, open_pin_id, close_pin_id):
        if Pin is None:
            raise RuntimeError("PicoDigitalMotor requires MicroPython machine.Pin")

        self.open_pin = Pin(open_pin_id, Pin.OUT)
        self.close_pin = Pin(close_pin_id, Pin.OUT)
        self.stop()

    def open(self):
        self.close_pin.value(0)
        self.open_pin.value(1)
        return False

    def close(self):
        self.open_pin.value(0)
        self.close_pin.value(1)
        return False

    def stop(self):
        self.open_pin.value(0)
        self.close_pin.value(0)


class PicoLimitSwitchPositionSensor:
    def __init__(self, open_pin_id, closed_pin_id):
        if Pin is None:
            raise RuntimeError("PicoLimitSwitchPositionSensor requires MicroPython machine.Pin")

        self.open_limit = Pin(open_pin_id, Pin.IN, Pin.PULL_UP)
        self.closed_limit = Pin(closed_pin_id, Pin.IN, Pin.PULL_UP)

    def is_open(self):
        # Assumes switches pull the pin low when pressed.
        return self.open_limit.value() == 0

    def is_closed(self):
        return self.closed_limit.value() == 0


class PicoStepper28BYJ48:
    """28BYJ-48 stepper motor through its driver board.

    Wire the driver's IN1-IN4 pins to the GPIOs in settings.py. The class uses a
    half-step sequence, which is common for the 28BYJ-48 and ULN2003 driver.
    """

    HALF_STEP_SEQUENCE = (
        (1, 0, 0, 0),
        (1, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 1, 1, 0),
        (0, 0, 1, 0),
        (0, 0, 1, 1),
        (0, 0, 0, 1),
        (1, 0, 0, 1),
    )

    def __init__(self, pin_ids, settings):
        if Pin is None:
            raise RuntimeError("PicoStepper28BYJ48 requires MicroPython machine.Pin")

        self.pins = [Pin(pin_id, Pin.OUT) for pin_id in pin_ids]
        self.settings = settings
        self.position = "closed"
        self.step_index = 0
        self.stop()

    def open(self):
        self._move(self.settings["stepper_steps_per_open"], 1)
        self.position = "open"
        return True

    def close(self):
        self._move(self.settings["stepper_steps_per_close"], -1)
        self.position = "closed"
        return True

    def stop(self):
        for pin in self.pins:
            pin.value(0)

    def _move(self, steps, direction):
        for _step in range(steps):
            self.step_index = (self.step_index + direction) % len(self.HALF_STEP_SEQUENCE)
            values = self.HALF_STEP_SEQUENCE[self.step_index]
            for index, value in enumerate(values):
                self.pins[index].value(value)
            self._sleep_ms(self.settings["stepper_step_delay_ms"])
        self.stop()

    def _sleep_ms(self, delay_ms):
        if time is None:
            return
        sleep_ms = getattr(time, "sleep_ms", None)
        if sleep_ms is not None:
            sleep_ms(delay_ms)
        else:
            time.sleep(delay_ms / 1000)
