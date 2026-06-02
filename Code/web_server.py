class LocalWebServer:
    """Placeholder for the future phone/computer dashboard."""

    def __init__(self, controller):
        self.controller = controller

    def status_payload(self):
        return self.controller.status()
