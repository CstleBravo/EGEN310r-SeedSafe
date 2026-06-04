DEFAULT_SETTINGS = {
    "feeding_start_hour": 7,
    "feeding_end_hour": 19,
    "cooldown_seconds": 1800,
    "motor_timeout_seconds": 20,
    "force_threshold": 500,
    "impact_threshold": 9000,
    "moisture_threshold": 600,
    "low_battery_voltage": 3.4,
    "battery_adc_reference_voltage": 3.3,
    "battery_voltage_divider_ratio": 2.0,
    "stepper_steps_per_open": 2048,
    "stepper_steps_per_close": 2048,
    "stepper_step_delay_ms": 2,
    "loop_delay_seconds": 1,
    "web_server_enabled": False,
    "web_server_host": "0.0.0.0",
    "web_server_port": 80,
}


PIN_MAP = {
    # These are placeholder GPIOs. Update them to match the final wiring.
    "stepper_in1": 10,
    "stepper_in2": 11,
    "stepper_in3": 12,
    "stepper_in4": 13,
    "mpu6050_sda": 4,
    "mpu6050_scl": 5,
    "mpu6050_i2c_id": 0,
    "mpu6050_address": 0x68,
    "dht11": 16,
    "pir_sensor": 17,
    "raindrop_adc": 26,
    "raindrop_digital": 18,
    "battery_adc": 28,
    "status_led": "LED",
}


def load_settings():
    """Return settings for now; later this can load a saved JSON file."""
    return DEFAULT_SETTINGS.copy()
