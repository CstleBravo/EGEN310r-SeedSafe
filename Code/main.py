from controller import SeedSafeController
from event_log import EventLogger
from hardware import (
    Clock,
    FakeMotor,
    FakePositionSensor,
    PicoDigitalMotor,
    PicoLimitSwitchPositionSensor,
    StatusLight,
)
from scheduler import ScheduleManager
from sensor import FakeSensors, PicoSensors
from settings import PIN_MAP, load_settings
from web_server import LocalWebServer


USE_REAL_PICO_HARDWARE = False


def build_controller(use_real_hardware=USE_REAL_PICO_HARDWARE):
    settings = load_settings()
    clock = Clock()

    if use_real_hardware:
        sensors = PicoSensors(settings, PIN_MAP)
        motor = PicoDigitalMotor(PIN_MAP["motor_open"], PIN_MAP["motor_close"])
        position_sensor = PicoLimitSwitchPositionSensor(
            PIN_MAP["open_limit"],
            PIN_MAP["closed_limit"],
        )
        status_light = StatusLight(PIN_MAP["status_led"])
    else:
        sensors = FakeSensors(settings)
        motor = FakeMotor()
        position_sensor = FakePositionSensor(motor)
        status_light = StatusLight()

    scheduler = ScheduleManager(settings, clock)
    logger = EventLogger()

    controller = SeedSafeController(
        settings,
        sensors,
        motor,
        position_sensor,
        scheduler,
        logger,
        clock,
    )
    status_light.on()
    return controller, clock, settings


def main():
    controller, clock, settings = build_controller()
    web_server = None
    controller.boot()

    if settings["web_server_enabled"]:
        web_server = LocalWebServer(
            controller,
            settings["web_server_host"],
            settings["web_server_port"],
        )
        web_server.start()

    while True:
        controller.tick()
        if web_server is not None:
            web_server.poll()
        print(controller.status())
        clock.sleep(settings["loop_delay_seconds"])


if __name__ == "__main__":
    main()
