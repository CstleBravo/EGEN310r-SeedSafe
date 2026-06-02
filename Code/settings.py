DEFAULT_SETTINGS = {
    "feeding_start_hour": 7,
    "feeding_end_hour": 19,
    "cooldown_seconds": 1800,
    "motor_timeout_seconds": 20,
    "force_threshold": 500,
    "moisture_threshold": 600,
    "low_battery_voltage": 3.4,
    "loop_delay_seconds": 1,
}


PIN_MAP = {
    "motor_open": 14,
    "motor_close": 15,
    "force_sensor_adc": 26,
    "moisture_sensor_adc": 27,
    "motion_sensor": 16,
    "battery_adc": 28,
    "open_limit": 17,
    "closed_limit": 18,
    "status_led": "LED",
}


def load_settings():
    """Return settings for now; later this can load a saved JSON file."""
    return DEFAULT_SETTINGS.copy()
