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
- `Code/web_server.py` is a placeholder for a future local dashboard.

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

- force sensor on an ADC pin,
- moisture sensor on an ADC pin,
- battery monitor on an ADC pin through a voltage divider,
- motion sensor on a digital input pin,
- open/closed limit switches on digital input pins,
- a simple two-pin motor driver with one open command pin and one close command
  pin.

The motor class is intentionally a placeholder. If the final corkscrew uses a
servo, stepper motor, or H-bridge with PWM speed control, only the motor class
should need major changes.

## Local Web Dashboard

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
