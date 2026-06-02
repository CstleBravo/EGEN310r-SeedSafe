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
