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
