import time
from datetime import timedelta
from typing import Callable, Dict

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from io.display_controller import DisplayController
from core.config import Configuration
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState
from models.application import Application
from core.path import PathTo

# Constants
DEFAULT_FONT_SIZE = 5


class Pomodoro(Application):
    def __init__(self, callbacks: Dict[str, Callable]):
        """
        Initialize the PomodoroScreen and callbacks.

        :param callbacks: Dict[str, Callable]: Dictionary of callback functions.
        """
        super().__init__(callbacks)
        if self.status == ServiceStatus.DISABLED:
            logger.info(
                f"[{self.__class__.__name__}] Stopped initialization due to disabled status."
            )
            return

        self.work_duration = timedelta(
            minutes=Configuration.get_from_app_config(
                self.__class__.__name__,
                "work_duration_in_minutes",
                required=True,
            )
        )
        if self.work_duration <= timedelta(seconds=0):
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                f"[{self.__class__.__name__}] Work duration must be greater than 0."
            )
        self.short_duration = timedelta(
            minutes=Configuration.get_from_app_config(
                self.__class__.__name__,
                "break_duration_in_minutes",
                required=True,
            )
        )
        if (
            self.short_duration <= timedelta(seconds=0)
            or self.short_duration >= self.work_duration
        ):
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                f"[{self.__class__.__name__}] Break duration must be greater than 0 and less than work duration."
            )
        self.long_duration = timedelta(
            minutes=Configuration.get_from_app_config(
                self.__class__.__name__,
                "long_break_duration_in_minutes",
                required=True,
            )
        )
        if (
            self.long_duration <= timedelta(seconds=0)
            or self.long_duration <= self.short_duration
        ):
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                f"[{self.__class__.__name__}] Long break duration must be greater than 0 and greater than short break duration."
            )
        self.active = False
        self.font = ImageFont.truetype(PathTo.FONT_FILE, DEFAULT_FONT_SIZE)
        self.canvas_width = DisplayController().led_cols
        self.canvas_height = DisplayController().led_rows
        self.cycle_order = "WSWSWL"
        self.cycle_idx = 0
        self.status = ""
        self.time_left = None
        self.last_update_time = None

        if self.status == ServiceStatus.ERROR_APP_CONFIG:
            logger.error(
                f"[{self.__class__.__name__}] Application configuration errors, please check the configuration before restarting."
            )
            return

        self.status = ServiceStatus.RUNNING
        logger.info(f"[{self.__class__.__name__}] Running.")

    def generate(self, tilt_state: TiltState, encoder_input: EncoderInput) -> Image:
        """
        Generate the frame for the Pomodoro app.

        :param tilt_state: TiltState: The current tilt state of the device.
        :param encoder_input: EncoderInput: The status of the encoder input.
        :return: Image: The generated frame.
        """
        super().generate(tilt_state, encoder_input)
        try:
            if encoder_input is EncoderInput.SINGLE_PRESS:
                self.active = not self.active
                self.last_update_time = time.time()
                if self.active and self.time_left is None:
                    status = self.cycle_order[self.cycle_idx]
                    if status == "W":
                        self.status = "W"
                        self.time_left = self.work_duration
                    elif status == "S":
                        self.status = "S"
                        self.time_left = self.short_duration
                    elif status == "L":
                        self.status = "L"
                        self.time_left = self.long_duration
                    self.cycle_idx += 1
                    if self.cycle_idx >= len(self.cycle_order):
                        self.cycle_idx = 0
            elif encoder_input is EncoderInput.INCREASE_CLOCKWISE:
                self.callbacks["switch_next_app"]()
            elif encoder_input is EncoderInput.DECREASE_COUNTERCLOCKWISE:
                self.callbacks["switch_prev_app"]()

            if self.active:
                self.time_left = self.time_left - timedelta(
                    seconds=(time.time() - self.last_update_time)
                )
                self.last_update_time = time.time()

                if self.time_left <= timedelta(seconds=0):
                    print("time is up")
                    self.active = False
                    self.time_left = None
                    self.last_update_time = None

            # if isHorizontal:
            #     frame = Image.new("RGB", (self.canvas_width, self.canvas_height), (0,0,0))
            #     draw = ImageDraw.Draw(frame)

            #     if self.time_left is not None:
            #         minutes, seconds = divmod(self.time_left.total_seconds(), 60)
            #         time_str = str(int(round(minutes))) + "m " + str(int(round(seconds))) + "s"
            #         draw.text((0,0), time_str, (255,255,255), font=self.font)

            #         if self.status != '':
            #             draw.text((0,7), self.status, (255,255,255), font=self.font)
            #     else:
            #         if self.status != '':
            #             draw.text((0,7), self.status + " is Over", (255,255,255), font=self.font)
            # else:
            bg_color = (255, 126, 109)
            if self.status == "W":
                bg_color = (255, 126, 109)
            elif self.status == "S":
                bg_color = (142, 202, 255)
            elif self.status == "L":
                bg_color = (43, 156, 255)

            frame = Image.new("RGB", (self.canvas_height, self.canvas_width), bg_color)
            draw = ImageDraw.Draw(frame)

            if self.status != "":
                if self.status == "W":
                    draw.text((1, 7), "Work", (255, 255, 255), font=self.font)
                elif self.status == "S":
                    draw.text((1, 7), "Short", (255, 255, 255), font=self.font)
                    draw.text((1, 13), "Break", (255, 255, 255), font=self.font)
                elif self.status == "L":
                    draw.text((1, 7), "Long", (255, 255, 255), font=self.font)
                    draw.text((1, 13), "Break", (255, 255, 255), font=self.font)

                if self.time_left is None:
                    y_loc = 19
                    if self.status == "W":
                        y_loc = 13
                    draw.text((1, y_loc), "Is Over", (255, 255, 255), font=self.font)
                else:
                    minutes, seconds = divmod(self.time_left.total_seconds(), 60)
                    time_str = (
                        str(int(round(minutes))) + "m " + str(int(round(seconds))) + "s"
                    )
                    draw.text((1, 1), time_str, (255, 255, 255), font=self.font)
            else:
                draw.text((0, 10), "POMODORO", (255, 255, 255), font=self.font)
                draw.text((7, 26), "PRESS", (255, 255, 255), font=self.font)
                draw.text((13, 32), "TO", (255, 255, 255), font=self.font)
                draw.text((7, 38), "START", (255, 255, 255), font=self.font)

            frame = frame.rotate(90, expand=True)

            return frame
        except Exception as e:
            self.status = ServiceStatus.ERROR_APP_INTERNAL
            logger.error(f"[PomodoroScreen App] Error generating frame: {e}")
            return self.generate_on_error()
            return self.generate_on_error()
