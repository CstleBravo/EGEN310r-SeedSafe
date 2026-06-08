try:
    import socket
except ImportError:
    socket = None

try:
    import ujson as json
except ImportError:
    import json


class PicoCommandServer:
    """Tiny TCP command server for a laptop-hosted dashboard.

    Protocol:
    - Client opens a TCP connection.
    - Client sends one line: STATUS, OPEN, CLOSE, RESET, or PING.
    - Pico replies with one JSON object and closes the connection.

    This keeps browser/HTML work off the Pico and leaves it with a small,
    predictable socket workload.
    """

    def __init__(self, controller, host="0.0.0.0", port=5050):
        self.controller = controller
        self.host = host
        self.port = port
        self.server_socket = None

    def start(self):
        if socket is None:
            raise RuntimeError("socket module is not available")

        addr = socket.getaddrinfo(self.host, self.port)[0][-1]
        self.server_socket = socket.socket()
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(addr)
        self.server_socket.listen(1)
        self.server_socket.settimeout(0)
        print("Command server listening on {}:{}".format(self.host, self.port))

    def poll(self):
        if self.server_socket is None:
            return

        try:
            client, _addr = self.server_socket.accept()
        except OSError:
            return

        try:
            self._configure_client_socket(client)
            command = self._read_command(client)
            response = self._handle_command(command)
            client.send((json.dumps(response) + "\n").encode())
        except Exception as exc:
            try:
                error_response = {
                    "ok": False,
                    "error": "Command server error: {}".format(exc),
                }
                client.send((json.dumps(error_response) + "\n").encode())
            except Exception:
                pass
        finally:
            client.close()

    def _read_command(self, client):
        request = client.recv(128)
        command = request.decode().strip().upper()
        if " " in command:
            command = command.split(" ", 1)[0]
        return command

    def _handle_command(self, command):
        if command == "PING":
            return {"ok": True, "message": "pong"}

        if command == "STATUS":
            return {"ok": True, "status": self._jsonable(self.controller.status())}

        if command == "OPEN":
            return {
                "ok": True,
                "command": "OPEN",
                "status": self._jsonable(self.controller.manual_open()),
            }

        if command == "CLOSE":
            return {
                "ok": True,
                "command": "CLOSE",
                "status": self._jsonable(self.controller.manual_close()),
            }

        if command == "RESET":
            return {
                "ok": True,
                "command": "RESET",
                "status": self._jsonable(self.controller.reset_fault()),
            }

        return {
            "ok": False,
            "error": "Unknown command",
            "allowed_commands": ["PING", "STATUS", "OPEN", "CLOSE", "RESET"],
        }

    def _configure_client_socket(self, client):
        try:
            client.settimeout(1)
        except AttributeError:
            pass

    def _jsonable(self, value):
        if isinstance(value, dict):
            converted = {}
            for key in value:
                converted[str(key)] = self._jsonable(value[key])
            return converted

        if isinstance(value, (list, tuple)):
            return [self._jsonable(item) for item in value]

        return value
