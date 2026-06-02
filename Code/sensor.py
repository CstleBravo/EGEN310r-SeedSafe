try:
    from machine import ADC, Pin
except ImportError:
    ADC = None
    Pin = None


class SensorReadings:
    def __init__(self, force_value, motion_detected, moisture_value, battery_voltage):
        self.force_value = force_value
        self.motion_detected = motion_detected
        self.moisture_value = moisture_value
        self.battery_voltage = battery_voltage


class FakeSensors:
    def __init__(self, settings):
        self.settings = settings
        self.force_value = 0
        self.motion_detected = False
        self.moisture_value = 0
        self.battery_voltage = 5.0

    def read_all(self):
        return SensorReadings(
            self.force_value,
            self.motion_detected,
            self.moisture_value,
            self.battery_voltage,
        )

    def contact_detected(self, readings):
        return readings.force_value >= self.settings["force_threshold"]

    def wet_detected(self, readings):
        return readings.moisture_value >= self.settings["moisture_threshold"]

    def battery_low(self, readings):
        return readings.battery_voltage <= self.settings["low_battery_voltage"]


class PicoSensors:
    """Real Pico sensor layer.

    This is still a rough hardware placeholder. It assumes analog force,
    moisture, and battery readings plus a digital motion pin.
    """

    def __init__(self, settings, pin_map):
        if ADC is None or Pin is None:
            raise RuntimeError("PicoSensors requires MicroPython machine.ADC and machine.Pin")

        self.settings = settings
        self.force_adc = ADC(pin_map["force_sensor_adc"])
        self.moisture_adc = ADC(pin_map["moisture_sensor_adc"])
        self.battery_adc = ADC(pin_map["battery_adc"])
        self.motion_pin = Pin(pin_map["motion_sensor"], Pin.IN)

    def read_all(self):
        force_value = self.force_adc.read_u16()
        moisture_value = self.moisture_adc.read_u16()
        battery_voltage = self._battery_voltage_from_adc(self.battery_adc.read_u16())

        return SensorReadings(
            force_value,
            self.motion_pin.value() == 1,
            moisture_value,
            battery_voltage,
        )

    def contact_detected(self, readings):
        return readings.force_value >= self.settings["force_threshold"]

    def wet_detected(self, readings):
        return readings.moisture_value >= self.settings["moisture_threshold"]

    def battery_low(self, readings):
        return readings.battery_voltage <= self.settings["low_battery_voltage"]

    def _battery_voltage_from_adc(self, raw_value):
        reference = self.settings["battery_adc_reference_voltage"]
        divider_ratio = self.settings["battery_voltage_divider_ratio"]
        return (raw_value / 65535) * reference * divider_ratio
