from controller import SeedSafeController
from event_log import EventLogger
from hardware import (
    Clock,
    FakeMotor,
    FakePositionSensor,
    PicoStepper28BYJ48,
    StatusLight,
)
from scheduler import ScheduleManager
from sensor import FakeSensors, PicoSensors
from settings import PIN_MAP, load_settings
from command_server import PicoCommandServer
from web_server import LocalWebServer


USE_REAL_PICO_HARDWARE = False


def build_controller(use_real_hardware=USE_REAL_PICO_HARDWARE):
    settings = load_settings()
    clock = Clock()

    if use_real_hardware:
        sensors = PicoSensors(settings, PIN_MAP)
        motor = PicoStepper28BYJ48(
            [
                PIN_MAP["stepper_in1"],
                PIN_MAP["stepper_in2"],
                PIN_MAP["stepper_in3"],
                PIN_MAP["stepper_in4"],
            ],
            settings,
        )
        position_sensor = FakePositionSensor(motor)
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
    command_server = None
    controller.boot()
    ip = None

    if settings["web_server_enabled"] or settings["command_server_enabled"]:
        from wifi import connect_to_wifi, wifi_supported

        if wifi_supported():
            from secrets import WIFI_SSID, WIFI_PASSWORD

            ip = connect_to_wifi(WIFI_SSID, WIFI_PASSWORD)
        else:
            ip = "127.0.0.1"

    if settings["web_server_enabled"]:
        print("Pico-hosted dashboard at:")
        print("http://{}:{}".format(ip, settings["web_server_port"]))
        web_server = LocalWebServer(
            controller,
            settings["web_server_host"],
            settings["web_server_port"],
        )
        web_server.start()

    if settings["command_server_enabled"]:
        print("Pico command server at:")
        print("{}:{}".format(ip, settings["command_server_port"]))
        command_server = PicoCommandServer(
            controller,
            settings["command_server_host"],
            settings["command_server_port"],
        )
        command_server.start()

    while True:
        controller.tick()
        if web_server is not None:
            web_server.poll()
        if command_server is not None:
            command_server.poll()
        print(controller.status())
        clock.sleep(settings["loop_delay_seconds"])


if __name__ == "__main__":
    main()
