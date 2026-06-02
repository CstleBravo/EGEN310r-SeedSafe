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
            if self.scheduler.feeding_window_is_active():
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
        self._handle_event(Events.MANUAL_OPEN)

    def manual_close(self):
        self._handle_event(Events.MANUAL_CLOSE)

    def reset_fault(self):
        self._handle_event(Events.RESET_FAULT)

    def status(self):
        return {
            "state": self.state_machine.state,
            "last_close_reason": self.state_machine.last_close_reason,
            "recent_events": self.logger.recent(),
        }

    def _handle_event(self, event):
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

    def _check_motor_timeout(self):
        if self.movement_started_at is None:
            return
        elapsed = self.clock.seconds() - self.movement_started_at
        if elapsed >= self.settings["motor_timeout_seconds"]:
            self._handle_event(Events.MOTOR_TIMEOUT)
