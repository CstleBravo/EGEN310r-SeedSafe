DEFAULT_SETTINGS = {
    "feeding_start_hour": 7,
    "feeding_end_hour": 19,
    "cooldown_seconds": 1800,
    "motor_timeout_seconds": 20,
    "manual_close_cooldown_seconds": 300,
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
    "command_server_enabled": True,
    "command_server_host": "0.0.0.0",
    "command_server_port": 5050,
}


PIN_MAP = {
    # Current motor wiring.
    "stepper_in1": 6,
    "stepper_in2": 7,
    "stepper_in3": 8,
    "stepper_in4": 9,
    # Optional sensors can be left as None until they are wired.
    "mpu6050_sda": None,
    "mpu6050_scl": None,
    "mpu6050_i2c_id": None,
    "mpu6050_address": None,
    "dht11": None,
    # Set this to the actual IR sensor output pin once chosen.
    "pir_sensor": None,
    # Use a digital GPIO for D0, and only use GP26/GP27/GP28 for A0.
    "raindrop_adc": None,
    "raindrop_digital": 18,
    "battery_adc": None,
    "status_led": "LED",
}


def load_settings():
    """Return settings for now; later this can load a saved JSON file."""
    return DEFAULT_SETTINGS.copy()
