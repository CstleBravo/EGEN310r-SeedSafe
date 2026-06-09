class ScheduleManager:
    def __init__(self, settings, clock):
        self.settings = settings
        self.clock = clock
        self.cooldown_until = None
        self.manual_hold_until = None

    def feeding_window_is_active(self):
        now = self.clock.now()
        hour = now[3]
        start = self.settings["feeding_start_hour"]
        end = self.settings["feeding_end_hour"]

        if start <= end:
            return start <= hour < end

        return hour >= start or hour < end

    def start_cooldown(self):
        self.cooldown_until = self.clock.seconds() + self.settings["cooldown_seconds"]

    def cooldown_has_expired(self):
        if self.cooldown_until is None:
            return True
        return self.clock.seconds() >= self.cooldown_until

    def start_manual_hold(self, duration_seconds=None):
        if duration_seconds is None:
            duration_seconds = self.settings["manual_close_cooldown_seconds"]
        self.manual_hold_until = self.clock.seconds() + duration_seconds

    def clear_manual_hold(self):
        self.manual_hold_until = None

    def manual_hold_is_active(self):
        if self.manual_hold_until is None:
            return False
        if self.clock.seconds() >= self.manual_hold_until:
            self.manual_hold_until = None
            return False
        return True

    def manual_hold_remaining_seconds(self):
        if not self.manual_hold_is_active():
            return 0
        return int(self.manual_hold_until - self.clock.seconds())
