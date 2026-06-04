try:
    from machine import ADC, I2C, Pin
except ImportError:
    ADC = None
    I2C = None
    Pin = None

try:
    import dht
except ImportError:
    dht = None


class SensorReadings:
    def __init__(
        self,
        force_value,
        motion_detected,
        moisture_value,
        battery_voltage,
        temperature_c=None,
        humidity_percent=None,
        acceleration_x=0,
        acceleration_y=0,
        acceleration_z=0,
        impact_value=0,
    ):
        self.force_value = force_value
        self.motion_detected = motion_detected
        self.moisture_value = moisture_value
        self.battery_voltage = battery_voltage
        self.temperature_c = temperature_c
        self.humidity_percent = humidity_percent
        self.acceleration_x = acceleration_x
        self.acceleration_y = acceleration_y
        self.acceleration_z = acceleration_z
        self.impact_value = impact_value


class FakeSensors:
    def __init__(self, settings):
        self.settings = settings
        self.force_value = 0
        self.motion_detected = False
        self.moisture_value = 0
        self.battery_voltage = 5.0
        self.temperature_c = 22
        self.humidity_percent = 40
        self.impact_value = 0

    def read_all(self):
        return SensorReadings(
            self.force_value,
            self.motion_detected,
            self.moisture_value,
            self.battery_voltage,
            self.temperature_c,
            self.humidity_percent,
            impact_value=self.impact_value,
        )

    def contact_detected(self, readings):
        return readings.impact_value >= self.settings["impact_threshold"]

    def wet_detected(self, readings):
        return readings.moisture_value >= self.settings["moisture_threshold"]

    def battery_low(self, readings):
        return readings.battery_voltage <= self.settings["low_battery_voltage"]


class PicoSensors:
    """Real Pico sensor layer.

    This assumes the current parts list:
    - MPU6050 accelerometer over I2C for impact/contact detection
    - DHT11 temperature/humidity sensor
    - PIR digital motion sensor
    - raindrop module with analog output, digital output, or both
    - optional battery voltage ADC
    """

    def __init__(self, settings, pin_map):
        if ADC is None or I2C is None or Pin is None:
            raise RuntimeError("PicoSensors requires MicroPython machine.ADC, I2C, and Pin")

        self.settings = settings
        self.pin_map = pin_map
        self.raindrop_adc = self._optional_adc(pin_map.get("raindrop_adc"))
        self.raindrop_digital = self._optional_input_pin(pin_map.get("raindrop_digital"))
        self.battery_adc = self._optional_adc(pin_map.get("battery_adc"))
        self.motion_pin = Pin(pin_map["pir_sensor"], Pin.IN)
        self.i2c = I2C(
            pin_map["mpu6050_i2c_id"],
            sda=Pin(pin_map["mpu6050_sda"]),
            scl=Pin(pin_map["mpu6050_scl"]),
        )
        self.mpu_address = pin_map["mpu6050_address"]
        self._wake_mpu6050()
        self.dht_sensor = None

        if dht is not None:
            self.dht_sensor = dht.DHT11(Pin(pin_map["dht11"]))

    def read_all(self):
        acceleration_x, acceleration_y, acceleration_z = self._read_acceleration()
        impact_value = self._impact_value(acceleration_x, acceleration_y, acceleration_z)
        moisture_value = self._read_moisture()
        battery_voltage = self._read_battery_voltage()
        temperature_c, humidity_percent = self._read_dht11()

        return SensorReadings(
            impact_value,
            self.motion_pin.value() == 1,
            moisture_value,
            battery_voltage,
            temperature_c,
            humidity_percent,
            acceleration_x,
            acceleration_y,
            acceleration_z,
            impact_value,
        )

    def contact_detected(self, readings):
        return readings.impact_value >= self.settings["impact_threshold"]

    def wet_detected(self, readings):
        return readings.moisture_value >= self.settings["moisture_threshold"]

    def battery_low(self, readings):
        return readings.battery_voltage <= self.settings["low_battery_voltage"]

    def _battery_voltage_from_adc(self, raw_value):
        reference = self.settings["battery_adc_reference_voltage"]
        divider_ratio = self.settings["battery_voltage_divider_ratio"]
        return (raw_value / 65535) * reference * divider_ratio

    def _optional_adc(self, pin_id):
        if pin_id is None:
            return None
        return ADC(pin_id)

    def _optional_input_pin(self, pin_id):
        if pin_id is None:
            return None
        return Pin(pin_id, Pin.IN)

    def _read_moisture(self):
        if self.raindrop_adc is not None:
            return self.raindrop_adc.read_u16()

        if self.raindrop_digital is not None:
            if self.raindrop_digital.value() == 1:
                return 65535
            return 0

        return 0

    def _read_battery_voltage(self):
        if self.battery_adc is None:
            return 5.0
        return self._battery_voltage_from_adc(self.battery_adc.read_u16())

    def _read_dht11(self):
        if self.dht_sensor is None:
            return None, None

        try:
            self.dht_sensor.measure()
            return self.dht_sensor.temperature(), self.dht_sensor.humidity()
        except OSError:
            return None, None

    def _wake_mpu6050(self):
        # PWR_MGMT_1 register. Writing 0 wakes the sensor from sleep.
        self.i2c.writeto_mem(self.mpu_address, 0x6B, b"\x00")

    def _read_acceleration(self):
        data = self.i2c.readfrom_mem(self.mpu_address, 0x3B, 6)
        x = self._signed_16(data[0], data[1])
        y = self._signed_16(data[2], data[3])
        z = self._signed_16(data[4], data[5])
        return x, y, z

    def _signed_16(self, high_byte, low_byte):
        value = (high_byte << 8) | low_byte
        if value & 0x8000:
            value = -((65535 - value) + 1)
        return value

    def _impact_value(self, x, y, z):
        # Rough magnitude approximation; avoids sqrt for MicroPython simplicity.
        return abs(x) + abs(y) + abs(z)
