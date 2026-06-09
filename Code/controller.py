from state_machine import Actions, Events, FeederStateMachine, States


class SeedSafeController:
    def __init__(self, settings, sensors, motor, position_sensor, scheduler, logger, clock):
        self.settings = settings
        self.sensors = sensors
        self.motor = motor
        self.position_sensor = position_sensor
        self.scheduler = scheduler
        self.logger = logger
        self.clock = clock
        self.state_machine = FeederStateMachine()
        self.movement_started_at = None

    def boot(self):
        result = self.state_machine.handle(Events.BOOT_COMPLETE)
        self.logger.record(self.clock, Events.BOOT_COMPLETE, result["new_state"])

    def tick(self):
        readings = self.sensors.read_all()

        if self.sensors.battery_low(readings):
            self._handle_event(Events.BATTERY_LOW)

        if self.state_machine.state == States.CLOSED_IDLE:
            if (
                self.scheduler.feeding_window_is_active()
                and not self.scheduler.manual_hold_is_active()
            ):
                self._handle_event(Events.FEEDING_WINDOW_STARTED)

        elif self.state_machine.state == States.OPENING:
            if self.position_sensor.is_open():
                self._handle_event(Events.OPEN_CONFIRMED)
            else:
                self._check_motor_timeout()

        elif self.state_machine.state == States.OPEN_MONITORING:
            if not self.scheduler.feeding_window_is_active():
                self._handle_event(Events.FEEDING_WINDOW_ENDED)
            elif self.sensors.contact_detected(readings):
                self._handle_event(Events.CONTACT_DETECTED)
            elif self.sensors.wet_detected(readings):
                self._handle_event(Events.WET_DETECTED)

        elif self.state_machine.state == States.CLOSING:
            if self.position_sensor.is_closed():
                self._handle_event(Events.CLOSE_CONFIRMED)
                if self.state_machine.state == States.CLOSED_COOLDOWN:
                    self.scheduler.start_cooldown()
            else:
                self._check_motor_timeout()

        elif self.state_machine.state == States.CLOSED_COOLDOWN:
            if self.scheduler.cooldown_has_expired():
                self._handle_event(Events.COOLDOWN_EXPIRED)

    def manual_open(self):
        self.scheduler.clear_manual_hold()
        self._handle_event(Events.MANUAL_OPEN)
        return self.status()

    def manual_close(self):
        self._handle_event(Events.MANUAL_CLOSE)
        return self.status()

    def reset_fault(self):
        self._handle_event(Events.RESET_FAULT)
        return self.status()

    def status(self):
        readings = self.sensors.read_all()

        return {
            "state": self.state_machine.state,
            "last_close_reason": self.state_machine.last_close_reason,
            "feeding_window_active": self.scheduler.feeding_window_is_active(),
            "manual_hold_active": self.scheduler.manual_hold_is_active(),
            "manual_hold_remaining_seconds": self.scheduler.manual_hold_remaining_seconds(),
            "sensors": {
                "force_value": readings.force_value,
                "impact_value": readings.impact_value,
                "motion_detected": readings.motion_detected,
                "moisture_value": readings.moisture_value,
                "battery_voltage": readings.battery_voltage,
                "temperature_c": readings.temperature_c,
                "humidity_percent": readings.humidity_percent,
                "acceleration_x": readings.acceleration_x,
                "acceleration_y": readings.acceleration_y,
                "acceleration_z": readings.acceleration_z,
            },
            "settings": {
                "feeding_start_hour": self.settings["feeding_start_hour"],
                "feeding_end_hour": self.settings["feeding_end_hour"],
                "cooldown_seconds": self.settings["cooldown_seconds"],
                "manual_close_cooldown_seconds": self.settings["manual_close_cooldown_seconds"],
                "impact_threshold": self.settings["impact_threshold"],
                "moisture_threshold": self.settings["moisture_threshold"],
                "low_battery_voltage": self.settings["low_battery_voltage"],
            },
            "recent_events": self.logger.recent(),
        }

    def _handle_event(self, event):
        if event in (Events.OPEN_CONFIRMED, Events.CLOSE_CONFIRMED):
            self._stop_motor_if_supported()

        result = self.state_machine.handle(event)
        if result["old_state"] != result["new_state"] or result["action"] != Actions.NONE:
            self.logger.record(self.clock, event, result["new_state"])
        self._run_action(result["action"])

    def _run_action(self, action):
        if action == Actions.OPEN_FEEDER:
            self.movement_started_at = self.clock.seconds()
            if self.motor.open():
                self._handle_event(Events.OPEN_CONFIRMED)
        elif action == Actions.CLOSE_FEEDER:
            self.movement_started_at = self.clock.seconds()
            if self.motor.close():
                self._handle_event(Events.CLOSE_CONFIRMED)
                if self.state_machine.state == States.CLOSED_COOLDOWN:
                    self.scheduler.start_cooldown()
                elif self.state_machine.last_close_reason == Events.MANUAL_CLOSE:
                    self.scheduler.start_manual_hold()

    def _check_motor_timeout(self):
        if self.movement_started_at is None:
            return
        elapsed = self.clock.seconds() - self.movement_started_at
        if elapsed >= self.settings["motor_timeout_seconds"]:
            self._handle_event(Events.MOTOR_TIMEOUT)

    def _stop_motor_if_supported(self):
        stop = getattr(self.motor, "stop", None)
        if stop is not None:
            stop()
