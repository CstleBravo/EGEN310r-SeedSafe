# Seed Safe

Rough starter code for the Seed Safe bear-proof bird feeder controller.

The goal is to build the project around a Raspberry Pi Pico WH running
MicroPython. The current code is intentionally hardware-light: it uses fake
sensors and a fake motor so the core state logic can be shaped before the Pico
and final sensors are available.

## Current Files

- `Code/main.py` starts the controller loop.
- `Code/controller.py` coordinates sensors, schedule, motor actions, and logs.
- `Code/state_machine.py` defines feeder states, events, and actions.
- `Code/scheduler.py` handles feeding windows and cooldown timing.
- `Code/sensor.py` currently contains fake sensor readings.
- `Code/hardware.py` currently contains fake motor, position, clock, and light objects.
- `Code/settings.py` stores early configuration values and future pin mapping.
- `Code/event_log.py` keeps a small in-memory event history.
- `Code/command_server.py` exposes a small Pico TCP command port.
- `Code/web_server.py` is the older Pico-hosted dashboard experiment.
- `desktop_dashboard.py` hosts the dashboard on a laptop and talks to the Pico
  command port.

## Planned Behavior

The feeder starts closed, opens during scheduled feeding hours, monitors for
contact or wet conditions, closes when needed, and enters a cooldown after
contact or moisture events. Low battery and motor timeout handling are included
as early safety concepts.

## Pico Hardware Mode

`Code/main.py` currently defaults to fake hardware so it can run on a laptop.
When the Pico WH and wiring are ready, set:

```python
USE_REAL_PICO_HARDWARE = True
```

Then update the placeholder GPIO values in `Code/settings.py`.

The current Pico hardware layer assumes:

- 28BYJ-48 stepper motor through its driver board,
- MPU6050 accelerometer over I2C for contact/impact detection,
- DHT11 temperature/humidity sensor,
- PIR motion sensor on a digital input pin,
- raindrop module with analog output, digital output, or both,
- optional battery monitor on an ADC pin through a voltage divider.

The stepper class uses a common 28BYJ-48 half-step sequence. The exact number
of steps to fully open or close the corkscrew will need to be calibrated once
the mechanism is assembled.

The MPU6050 is currently used as a rough contact/impact sensor. It does not
identify a bear; it detects strong motion/contact with the feeder body.

## Recommended Dashboard Setup

The current recommended setup is to let the Pico handle only a tiny TCP command
server, then host the actual dashboard from a laptop. This avoids asking the
Pico to build and serve browser pages while it is also reading sensors and
moving the feeder.

On the Pico, `Code/settings.py` defaults to:

```python
"web_server_enabled": False,
"command_server_enabled": True,
"command_server_port": 5050,
```

Run `Code/main.py` on the Pico. It prints the Pico IP address and command port,
for example:

```text
Pico command server at:
192.168.1.42:5050
```

On the laptop, run:

```bash
python desktop_dashboard.py --pico-host 192.168.1.42 --pico-port 5050
```

Then open:

```text
http://127.0.0.1:8080
```

The laptop dashboard sends one-line commands to the Pico:

- `STATUS`
- `OPEN`
- `CLOSE`
- `RESET`
- `PING`

Each command receives one JSON response and closes the socket.

## Older Pico-Hosted Web Dashboard

`Code/web_server.py` contains a tiny socket-based dashboard and API skeleton.

It supports:

- `/` for a simple HTML status page,
- `/api/status` for feeder state, sensors, settings, and recent events,
- `/api/events` for recent event history,
- `/api/settings` for current editable settings,
- `/api/commands/open` for manual open,
- `/api/commands/close` for manual close,
- `/api/commands/reset` for fault reset.

The older dashboard links still work:

- `/status`
- `/open`
- `/close`
- `/reset`

The server is disabled by default in `Code/settings.py`:

```python
"web_server_enabled": False
```

On the Pico, the Wi-Fi connection setup still needs to be added before enabling
the server. The dashboard intentionally uses only simple sockets so it can stay
small enough for MicroPython.
