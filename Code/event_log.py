class EventLogger:
    def __init__(self, max_events=50):
        self.max_events = max_events
        self.events = []

    def record(self, clock, event_type, details=""):
        event = {
            "time": clock.now(),
            "type": event_type,
            "details": details,
        }
        self.events.append(event)

        if len(self.events) > self.max_events:
            self.events.pop(0)

    def recent(self):
        return self.events
