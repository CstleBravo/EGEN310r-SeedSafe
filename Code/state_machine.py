class States:
    STARTUP = "STARTUP"
    CLOSED_IDLE = "CLOSED_IDLE"
    OPENING = "OPENING"
    OPEN_MONITORING = "OPEN_MONITORING"
    CLOSING = "CLOSING"
    CLOSED_COOLDOWN = "CLOSED_COOLDOWN"
    LOW_POWER = "LOW_POWER"
    FAULT = "FAULT"
    MANUAL_CONTROL = "MANUAL_CONTROL"


class Events:
    BOOT_COMPLETE = "BOOT_COMPLETE"
    FEEDING_WINDOW_STARTED = "FEEDING_WINDOW_STARTED"
    FEEDING_WINDOW_ENDED = "FEEDING_WINDOW_ENDED"
    CONTACT_DETECTED = "CONTACT_DETECTED"
    WET_DETECTED = "WET_DETECTED"
    BATTERY_LOW = "BATTERY_LOW"
    OPEN_CONFIRMED = "OPEN_CONFIRMED"
    CLOSE_CONFIRMED = "CLOSE_CONFIRMED"
    COOLDOWN_EXPIRED = "COOLDOWN_EXPIRED"
    MOTOR_TIMEOUT = "MOTOR_TIMEOUT"
    MANUAL_OPEN = "MANUAL_OPEN"
    MANUAL_CLOSE = "MANUAL_CLOSE"
    RESET_FAULT = "RESET_FAULT"


class Actions:
    NONE = "NONE"
    OPEN_FEEDER = "OPEN_FEEDER"
    CLOSE_FEEDER = "CLOSE_FEEDER"
    ENTER_LOW_POWER = "ENTER_LOW_POWER"
    ENTER_FAULT = "ENTER_FAULT"


class FeederStateMachine:
    def __init__(self):
        self.state = States.STARTUP
        self.last_close_reason = None

    def handle(self, event):
        old_state = self.state
        action = Actions.NONE

        if self.state == States.STARTUP:
            if event == Events.BOOT_COMPLETE:
                self.state = States.CLOSED_IDLE

        elif self.state == States.CLOSED_IDLE:
            if event == Events.BATTERY_LOW:
                self.state = States.LOW_POWER
                action = Actions.ENTER_LOW_POWER
            elif event == Events.FEEDING_WINDOW_STARTED:
                self.state = States.OPENING
                action = Actions.OPEN_FEEDER
            elif event == Events.MANUAL_OPEN:
                self.state = States.MANUAL_CONTROL
                action = Actions.OPEN_FEEDER

        elif self.state == States.OPENING:
            if event == Events.OPEN_CONFIRMED:
                self.state = States.OPEN_MONITORING
            elif event == Events.MOTOR_TIMEOUT:
                self.state = States.FAULT
                action = Actions.ENTER_FAULT

        elif self.state == States.OPEN_MONITORING:
            if event in (Events.CONTACT_DETECTED, Events.WET_DETECTED):
                self.last_close_reason = event
                self.state = States.CLOSING
                action = Actions.CLOSE_FEEDER
            elif event == Events.FEEDING_WINDOW_ENDED:
                self.last_close_reason = event
                self.state = States.CLOSING
                action = Actions.CLOSE_FEEDER
            elif event == Events.BATTERY_LOW:
                self.last_close_reason = event
                self.state = States.CLOSING
                action = Actions.CLOSE_FEEDER
            elif event == Events.MANUAL_CLOSE:
                self.last_close_reason = event
                self.state = States.MANUAL_CONTROL
                action = Actions.CLOSE_FEEDER

        elif self.state == States.CLOSING:
            if event == Events.CLOSE_CONFIRMED:
                if self.last_close_reason in (Events.CONTACT_DETECTED, Events.WET_DETECTED):
                    self.state = States.CLOSED_COOLDOWN
                elif self.last_close_reason == Events.BATTERY_LOW:
                    self.state = States.LOW_POWER
                else:
                    self.state = States.CLOSED_IDLE
            elif event == Events.MOTOR_TIMEOUT:
                self.state = States.FAULT
                action = Actions.ENTER_FAULT

        elif self.state == States.CLOSED_COOLDOWN:
            if event == Events.BATTERY_LOW:
                self.state = States.LOW_POWER
                action = Actions.ENTER_LOW_POWER
            elif event == Events.COOLDOWN_EXPIRED:
                self.state = States.CLOSED_IDLE

        elif self.state == States.LOW_POWER:
            if event == Events.RESET_FAULT:
                self.state = States.CLOSED_IDLE

        elif self.state == States.FAULT:
            if event == Events.RESET_FAULT:
                self.state = States.CLOSED_IDLE

        elif self.state == States.MANUAL_CONTROL:
            if event == Events.OPEN_CONFIRMED:
                self.state = States.OPEN_MONITORING
            elif event == Events.CLOSE_CONFIRMED:
                self.state = States.CLOSED_IDLE
            elif event == Events.MOTOR_TIMEOUT:
                self.state = States.FAULT
                action = Actions.ENTER_FAULT

        return {
            "old_state": old_state,
            "event": event,
            "new_state": self.state,
            "action": action,
        }
