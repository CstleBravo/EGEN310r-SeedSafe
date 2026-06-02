class ScheduleManager:
    def __init__(self, settings, clock):
        self.settings = settings
        self.clock = clock
        self.cooldown_until = None

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
