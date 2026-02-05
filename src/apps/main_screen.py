import calendar
import os
import time
from datetime import datetime
from typing import Callable, Dict

from dateutil import tz
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from io.display_controller import DisplayController
from core.config import Configuration
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState
from models.application import Application
from core.path import PathTo

light_pink = (255, 219, 218)
dark_pink = (219, 127, 142)
white = (230, 255, 255)

salmon = (255, 150, 162)
tan = (255, 205, 178)
orange_tinted_white = (248, 237, 235)

washed_out_navy = (109, 104, 117)

discordColor = (150, 170, 255)
messengerColor = (60, 220, 255)
snapchatColor = (255, 252, 0)
smsColor = (110, 255, 140)

spotify_color = (0, 255, 0)

FONT_SIZE = 5


class MainScreen(Application):
    def __init__(self, callbacks: Dict[str, Callable]):
        """
        Initialize the MainScreen with callbacks.

        :param callbacks: Dict[str, Callable]: Dictionary of callback functions.
        """
        super().__init__(callbacks)
        if self.status == ServiceStatus.DISABLED:
            logger.info(
                f"[{self.__class__.__name__}] Stopped initialization due to disabled status."
            )
            return

        self.use_24_hour = Configuration.get_from_app_config(
            self.__class__.__name__, "use_24_hour", required=True
        )
        if self.use_24_hour not in [True, False]:
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                "Invalid use_24_hour value. Must be True or False."
            )
        self.date_format = Configuration.get_from_app_config(
            self.__class__.__name__, "date_format", required=True
        )
        if self.date_format != "MM-DD" and self.date_format != "DD-MM":
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                "Invalid date format. Possible values are 'MM-DD' or 'DD-MM'."
            )
        self.cycle_duration_in_seconds = Configuration.get_from_app_config(
            self.__class__.__name__, "cycle_duration_in_seconds", required=True
        )
        if self.cycle_duration_in_seconds <= 0:
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                "Invalid cycle duration in seconds. Must be greater than 0."
            )
        try:
            self.font = ImageFont.truetype(PathTo.FONT_FILE, FONT_SIZE)
            logger.info("Font loaded successfully.")
        except Exception as e:
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(f"Failed to load font: {e}")

        self.lastGenerateCall = None
        self.is_on_cycle = True
        self.currentIdx = 0
        self.selectMode = False
        # self.old_noti_list = []
        self.queued_frames = []

        try:
            self.backgrounds = {
                "sakura": Image.open(
                    os.path.join(PathTo.MAIN_SCREEN_BACKGROUND_FOLDER, "sakura-bg.png")
                ).convert("RGB"),
                "cloud": Image.open(
                    os.path.join(
                        PathTo.MAIN_SCREEN_BACKGROUND_FOLDER, "cloud-bg-clear.png"
                    )
                ).convert("RGBA"),
                "forest": Image.open(
                    os.path.join(PathTo.MAIN_SCREEN_BACKGROUND_FOLDER, "forest-bg.png")
                ).convert("RGB"),
            }
        except Exception as e:
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(f"Failed to load backgrounds: {e}")

        self.theme_list = [
            self.generate_sakura_bg,
            self.generate_cloud_bg,
            self.generate_forest_bg,
        ]

        if self.status == ServiceStatus.ERROR_APP_CONFIG:
            logger.error(
                f"[{self.__class__.__name__}] Application configuration errors, please check the configuration before restarting."
            )
            return

        self.status = ServiceStatus.RUNNING
        logger.info(f"[{self.__class__.__name__}] Running.")

        self.last_sakura_frame = None
        self.last_sakura_time = None
        self.last_sakura_on_cycle = None

        self.last_cloud_frame = None
        self.last_cloud_time = None

        self.last_forest_frame = None

    def generate(self, tilt_state: TiltState, encoder_input: EncoderInput) -> Image:
        """
        Generate the frame for the MainScreen app.

        :param tilt_state: TiltState: The current tilt state of the device.
        :param encoder_input: EncoderInput: The status of the encoder input.
        :return: Image: The generated frame.
        """
        super().generate(tilt_state, encoder_input)
        try:
            if encoder_input == EncoderInput.LONG_PRESS:
                self.selectMode = not self.selectMode

            if self.selectMode:
                if encoder_input is EncoderInput.INCREASE_CLOCKWISE:
                    self.currentIdx += 1
                    self.queued_frames = []
                elif encoder_input is EncoderInput.DECREASE_COUNTERCLOCKWISE:
                    self.currentIdx -= 1
                    self.queued_frames = []
            else:
                if encoder_input is EncoderInput.SINGLE_PRESS:
                    self.callbacks["toggle_display"]()
                elif encoder_input is EncoderInput.INCREASE_CLOCKWISE:
                    self.callbacks["switch_next_app"]()
                elif encoder_input is EncoderInput.DECREASE_COUNTERCLOCKWISE:
                    self.callbacks["switch_prev_app"]()

            if self.lastGenerateCall is None:
                self.lastGenerateCall = time.time()
            if time.time() - self.lastGenerateCall >= self.cycle_duration_in_seconds:
                self.is_on_cycle = not self.is_on_cycle
                self.lastGenerateCall = time.time()

            frame = self.theme_list[self.currentIdx % len(self.theme_list)]()

            if self.selectMode:
                frame = frame.copy()
                draw = ImageDraw.Draw(frame)
                draw.rectangle(
                    (0, 0, DisplayController().led_cols - 1, DisplayController().led_rows - 1), outline=white
                )

            return frame
        except Exception as e:
            self.status = ServiceStatus.ERROR_APP_INTERNAL
            logger.error(f"Error generating frame: {e}")
            return self.generate_on_error()

    def generate_sakura_bg(self):
        current_time = datetime.now(tz=tz.tzlocal())

        if (
            self.last_sakura_frame is not None
            and self.last_sakura_time is not None
            and current_time.minute == self.last_sakura_time.minute
            and current_time.hour == self.last_sakura_time.hour
            and self.is_on_cycle == self.last_sakura_on_cycle
        ):
            return self.last_sakura_frame

        month = current_time.month
        day = current_time.day
        hours = current_time.hour
        if not self.use_24_hour:
            hours = hours % 12
            if hours == 0:
                hours += 12
        minutes = current_time.minute

        frame = self.backgrounds["sakura"].copy()
        draw = ImageDraw.Draw(frame)

        draw.text((3, 6), format_to_two_digits(hours), light_pink, font=self.font)
        draw.text((10, 6), ":", light_pink, font=self.font)
        draw.text((13, 6), format_to_two_digits(minutes), light_pink, font=self.font)

        if self.is_on_cycle:
            if self.date_format == "MM-DD":
                # date
                draw.text(
                    (23, 6), format_to_two_digits(month), dark_pink, font=self.font
                )
                draw.text((30, 6), ".", dark_pink, font=self.font)
                draw.text((33, 6), format_to_two_digits(day), dark_pink, font=self.font)
            else:
                # date
                draw.text((23, 6), format_to_two_digits(day), dark_pink, font=self.font)
                draw.text((30, 6), ".", dark_pink, font=self.font)
                draw.text(
                    (33, 6), format_to_two_digits(month), dark_pink, font=self.font
                )
        else:
            # dayOfWeek
            day_abbreviation = calendar.day_abbr[current_time.weekday()].upper()
            draw.text((23, 6), day_abbreviation, dark_pink, font=self.font)

        # notifications
        # noti_list = self.modules["notifications"].get_notification_list()
        # if noti_list is not None:
        #     counts = notification_count_dictionary(noti_list)

        #     if counts["Discord"] > 0:
        #         draw.rectangle((37, 26, 38, 27), fill=discordColor)
        #     if counts["SMS"] > 0:
        #         draw.rectangle((34, 26, 35, 27), fill=smsColor)
        #     if counts["Snapchat"] > 0:
        #         draw.rectangle((34, 29, 35, 30), fill=snapchatColor)
        #     if counts["Messenger"] > 0:
        #         draw.rectangle((37, 29, 38, 30), fill=messengerColor)

        #     self.old_noti_list = noti_list

        #     self.old_noti_list = noti_list

        self.last_sakura_frame = frame
        self.last_sakura_time = current_time
        self.last_sakura_on_cycle = self.is_on_cycle

        return frame

    def generate_cloud_bg(self):
        currentTime = datetime.now(tz=tz.tzlocal())

        if (
            self.last_cloud_frame is not None
            and self.last_cloud_time is not None
            and currentTime.second == self.last_cloud_time.second
        ):
            return self.last_cloud_frame

        month = currentTime.month
        day = currentTime.day
        hours = currentTime.hour
        if not self.use_24_hour:
            hours = hours % 12
            if hours == 0:
                hours += 12
        minutes = currentTime.minute
        seconds = currentTime.second

        # noti_list = self.modules["notifications"].get_notification_list()
        # if noti_list is not None:
        #     threading.Thread(
        #         target=generateNotiFramesAsync,
        #         args=(
        #             self.queued_frames,
        #             noti_list,
        #             self.old_noti_list.copy(),
        #             self.font,
        #             Board.led_cols,
        #             Board.led_rows,
        #         ),
        #     ).start()

        #     self.old_noti_list = noti_list.copy()

        if len(self.queued_frames) == 0:
            frame = Image.new("RGBA", (DisplayController().led_cols, DisplayController().led_rows), washed_out_navy)
        else:
            frame = self.queued_frames.pop(0)
        draw = ImageDraw.Draw(frame)

        frame.paste(self.backgrounds["cloud"], (0, 0), self.backgrounds["cloud"])

        time_x_off = 2
        time_y_off = 25
        draw.text(
            (time_x_off, time_y_off),
            format_to_two_digits(hours),
            orange_tinted_white,
            font=self.font,
        )
        draw.text(
            (time_x_off + 7, time_y_off), ":", orange_tinted_white, font=self.font
        )
        draw.text(
            (time_x_off + 10, time_y_off),
            format_to_two_digits(minutes),
            orange_tinted_white,
            font=self.font,
        )
        draw.text(
            (time_x_off + 17, time_y_off), ":", orange_tinted_white, font=self.font
        )
        draw.text(
            (time_x_off + 20, time_y_off),
            format_to_two_digits(seconds),
            orange_tinted_white,
            font=self.font,
        )

        date_x_off = 45
        date_y_off = 25
        if self.date_format == "MM-DD":
            draw.text(
                (date_x_off, date_y_off),
                format_to_two_digits(month),
                orange_tinted_white,
                font=self.font,
            )
            draw.text(
              
                (date_x_off + 7, date_y_off), ".", orange_tinted_white, font=self.font
            )
            draw.text(
                (date_x_off + 10, date_y_off),
                format_to_two_digits(day),
                orange_tinted_white,
                font=self.font,
            )
        else:
            draw.text(
                (date_x_off, date_y_off),
                format_to_two_digits(day),
                orange_tinted_white,
                font=self.font,
            )
            draw.text(
                (date_x_off + 7, date_y_off), ".", orange_tinted_white, font=self.font
            )
            draw.text(
                (date_x_off + 10, date_y_off),
                format_to_two_digits(month),
                orange_tinted_white,
                font=self.font,
            )

        self.last_cloud_frame = frame
        self.last_cloud_time = currentTime

        return frame.convert("RGB")

    def generate_forest_bg(self):
        if self.last_forest_frame is not None:
            return self.last_forest_frame
        frame = self.backgrounds["forest"].copy()
        self.last_forest_frame = frame
        return frame


def format_to_two_digits(number):
    return f"{number:02}"


# def notification_count_dictionary(noti_list):
#     counts = {"Discord": 0, "SMS": 0, "Snapchat": 0, "Messenger": 0}
#     for noti in noti_list:
#         if noti.application in counts.keys():
#             counts[noti.application] = counts[noti.application] + 1
#     return counts


# def generateNotiFramesAsync(
#     queue, noti_list, old_noti_list, font, canvas_width, canvas_height
# ):
#     for noti in noti_list:
#         found = False
#         for old_noti in old_noti_list:
#             if noti.noti_id == old_noti.noti_id:
#                 found = True
#         if not found:
#             color = (0, 0, 0)
#             if noti.application == "Discord":
#                 color = discordColor
#             elif noti.application == "SMS":
#                 color = smsColor
#             elif noti.application == "Snapchat":
#                 color = snapchatColor
#             elif noti.application == "Messenger":
#                 color = messengerColor

#             for _ in range(3):
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), color))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), color))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0)))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0)))

#             noti_str = (
#                 noti.application + " | Title: " + noti.title + " | Body: " + noti.body
#             )
#             noti_len = font.getsize(noti_str)[0]

#             for i in range(noti_len + canvas_width):
#                 noti_frame = Image.new("RGB", (canvas_width, canvas_height), color)
#                 noti_draw = ImageDraw.Draw(noti_frame)
#                 noti_draw.text(
#                     (canvas_width - i, 1), noti_str, orange_tinted_white, font
#                 )
#                 queue.append(noti_frame)

#             for _ in range(3):
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), color))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), color))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0)))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0)))
#                 queue.append(Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0)))
