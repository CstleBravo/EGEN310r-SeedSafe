try:
    import socket
except ImportError:
    socket = None


class LocalWebServer:
    """Tiny local web server for a phone/computer dashboard.

    This intentionally avoids web frameworks so it can run on MicroPython.
    It is a rough skeleton for local testing and Pico development.
    """

    def __init__(self, controller, host="0.0.0.0", port=80):
        self.controller = controller
        self.host = host
        self.port = port
        self.server_socket = None

    def status_payload(self):
        return self.controller.status()

    def start(self):
        if socket is None:
            raise RuntimeError("socket module is not available")

        addr = socket.getaddrinfo(self.host, self.port)[0][-1]
        self.server_socket = socket.socket()
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(addr)
        self.server_socket.listen(1)
        self.server_socket.settimeout(0)
        print("Web server listening on http://{}:{}".format(self.host, self.port))

    def poll(self):
        """Handle one waiting request, then return quickly to the controller loop."""
        if self.server_socket is None:
            return

        try:
            client, _addr = self.server_socket.accept()
        except OSError:
            return

        try:
            self._configure_client_socket(client)
            try:
                request = client.recv(1024)
            except OSError as exc:
                print("Web receive error:", exc)
                return
            method, path = self._request_line_from_request(request)
            try:
                status_code, content_type, body = self._handle_request(method, path)
            except Exception as exc:
                print("Web request error:", exc)
                status_code = 500
                content_type = "text/plain"
                body = "Internal server error"
            self._send_response(client, status_code, content_type, body)
        finally:
            client.close()

    def _request_line_from_request(self, request):
        try:
            request_text = request.decode()
            first_line = request_text.split("\r\n", 1)[0]
            parts = first_line.split(" ")
            if len(parts) >= 2:
                return parts[0], parts[1]
        except Exception:
            pass
        return "GET", "/"

    def _handle_request(self, method, path):
        if path == "/":
            return 200, "text/html", self._dashboard_html()

        if path in ("/status", "/api/status"):
            return 200, "application/json", self._status_json()

        if path in ("/events", "/api/events"):
            return 200, "application/json", self._events_json()

        if path == "/api/settings":
            return 200, "application/json", self._settings_json()

        if path in ("/open", "/api/commands/open"):
            self.controller.manual_open()
            if path.startswith("/api/"):
                return 200, "application/json", self._command_json("open")
            return 303, "text/plain", "Opening feeder"

        if path in ("/close", "/api/commands/close"):
            self.controller.manual_close()
            if path.startswith("/api/"):
                return 200, "application/json", self._command_json("close")
            return 303, "text/plain", "Closing feeder"

        if path in ("/reset", "/api/commands/reset"):
            self.controller.reset_fault()
            if path.startswith("/api/"):
                return 200, "application/json", self._command_json("reset")
            return 303, "text/plain", "Reset requested"

        return 404, "text/plain", "Not found"

    def _send_response(self, client, status_code, content_type, body):
        reason = {
            200: "OK",
            303: "See Other",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(status_code, "OK")

        headers = [
            "HTTP/1.1 {} {}".format(status_code, reason),
            "Content-Type: {}".format(content_type),
            "Content-Length: {}".format(len(body)),
        ]

        if status_code == 303:
            headers.append("Location: /")

        response = "\r\n".join(headers) + "\r\n\r\n" + body
        client.send(response.encode())

    def _configure_client_socket(self, client):
        try:
            client.settimeout(1)
        except AttributeError:
            pass

    def _dashboard_html(self):
        status = self.controller.status()
        recent_events = status["recent_events"]
        event_items = ""

        for event in recent_events[-10:]:
            event_items += "<li>{}: {} {}</li>".format(
                event["time"],
                event["type"],
                event["details"],
            )

        return """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{
    background:#0f172a;
    color:white;
    font-family:Arial;
    padding:20px;
}}
.card{{
    background:#1e293b;
    border-radius:12px;
    padding:15px;
    margin-bottom:15px;
}}
.button{{
    background:#14b8a6;
    color:white;
    padding:12px 18px;
    text-decoration:none;
    border-radius:8px;
    margin-right:10px;
}}
.button-danger{{
    background:#ef4444;
}}
</style>
</head>
<body>
<h1>Seed Safe</h1>
<div class="card">
<h2>Status</h2>
<p>State: {state}</p>
<p>Last Close Reason: {last_close_reason}</p>
</div>
<div class="card">
<h2>Manual Controls</h2>
<a class="button" href="/open">Open Feeder</a>
<a class="button button-danger" href="/close">Close Feeder</a>
<a class="button" href="/reset">Reset Fault</a>
</div>
<div class="card">
<h2>Recent Events</h2>
<ul>{event_items}</ul>
</div>
</body>
</html>""".format(
            state=status["state"],
            last_close_reason=status["last_close_reason"],
            event_items=event_items,
        )

    def _status_json(self):
        status = self.controller.status()

        return (
            '{{"state":{},"last_close_reason":{},"feeding_window_active":{},'
            '"sensors":{},"settings":{},"recent_events":{}}}'
        ).format(
            self._json_value(status["state"]),
            self._json_value(status["last_close_reason"]),
            self._json_bool(status["feeding_window_active"]),
            self._json_object(status["sensors"]),
            self._json_object(status["settings"]),
            self._events_array(status["recent_events"][-10:]),
        )

    def _events_json(self):
        status = self.controller.status()
        return '{{"recent_events":{}}}'.format(
            self._events_array(status["recent_events"][-20:])
        )

    def _settings_json(self):
        return self._json_object(self.controller.status()["settings"])

    def _command_json(self, command):
        return '{{"command":"{}","status":{}}}'.format(
            command,
            self._status_json(),
        )

    def _events_array(self, events):
        event_strings = []

        for event in events:
            event_strings.append(
                '{{"time":"{}","type":"{}","details":"{}"}}'.format(
                    self._json_string(event["time"]),
                    self._json_string(event["type"]),
                    self._json_string(event["details"]),
                )
            )

        return "[{}]".format(",".join(event_strings))

    def _json_object(self, values):
        pairs = []

        for key in values:
            pairs.append(
                '"{}":{}'.format(
                    self._json_string(key),
                    self._json_value(values[key]),
                )
            )

        return "{{{}}}".format(",".join(pairs))

    def _json_value(self, value):
        if isinstance(value, bool):
            return self._json_bool(value)
        if isinstance(value, int) or isinstance(value, float):
            return str(value)
        if value is None:
            return "null"
        return '"{}"'.format(self._json_string(value))

    def _json_bool(self, value):
        if value:
            return "true"
        return "false"

    def _json_string(self, value):
        text = str(value)
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        return text
