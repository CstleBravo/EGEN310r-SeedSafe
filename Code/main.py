from controller import SeedSafeController
from event_log import EventLogger
from hardware import Clock, FakeMotor, FakePositionSensor, StatusLight
from scheduler import ScheduleManager
from sensor import FakeSensors
from settings import load_settings


def build_controller():
    settings = load_settings()
    clock = Clock()
    sensors = FakeSensors(settings)
    motor = FakeMotor()
    position_sensor = FakePositionSensor(motor)
    scheduler = ScheduleManager(settings, clock)
    logger = EventLogger()
    status_light = StatusLight()

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
    controller.boot()

    while True:
        controller.tick()
        print(controller.status())
        clock.sleep(settings["loop_delay_seconds"])


if __name__ == "__main__":
    main()
