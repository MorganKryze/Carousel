from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from enums.service_status import ServiceStatus
from utils.path import PathTo

# Constants
FONT_SIZE = 5

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GRAY = (128, 128, 128)
GREEN = (0, 255, 0)


class CustomFrames:
    """Custom frames for the application."""

    led_rows: int
    led_cols: int
    font = ImageFont.truetype(PathTo.FONT_FILE, FONT_SIZE)

    @classmethod
    def init(cls, led_rows: int, led_cols: int) -> None:
        """Initialize custom frames."""

        cls.led_rows = led_rows
        cls.led_cols = led_cols
        logger.debug("Custom frames initialized.")

    @classmethod
    def loading(cls, percentage: int) -> Image:
        """
        Generate a loading frame with the given percentage.

        :param percentage: The loading percentage.
        :return: Image: The loading frame.
        """
        frame = cls.black()
        draw = ImageDraw.Draw(frame)
        bar_width = cls.led_cols - 30
        bar_height = 5
        bar_x = (cls.led_cols - bar_width) // 2
        filled_width = int((percentage / 100) * bar_width)
        draw.rectangle(
            (
                bar_x,
                cls.led_rows // 2 - bar_height // 2,
                bar_x + filled_width,
                cls.led_rows // 2 + bar_height // 2,
            ),
            fill=GREEN,
        )
        draw.rectangle(
            (
                bar_x,
                cls.led_rows // 2 - bar_height // 2,
                bar_x + bar_width,
                cls.led_rows // 2 + bar_height // 2,
            ),
            outline=GRAY,
            width=1,
        )
        return frame

    @classmethod
    def black(cls) -> Image:
        """
        Generate a black screen frame.

        :return: Image: The black screen frame.
        """
        return Image.new("RGB", (cls.led_cols, cls.led_rows), BLACK)

    @classmethod
    def error(cls, error_status: ServiceStatus) -> Image:
        """
        Generate an error frame with the provided error status.

        :param error_status: The status of the application.
        :return: Image: The error frame.
        """
        if (
            error_status == ServiceStatus.INITIALIZING
            or error_status == ServiceStatus.RUNNING
        ):
            logger.error(
                f"The app is not going under availability issue. status: {error_status.name}"
            )
            return cls.black()

        error_status_description = {
            ServiceStatus.DISABLED: "The app is disabled.",
            ServiceStatus.ERROR_NO_INTERNET: "No Internet connection.",
            ServiceStatus.ERROR_SERVER: "External server error.",
            ServiceStatus.ERROR_MODULE_CONFIG: "Module configuration error.",
            ServiceStatus.ERROR_MODULE_INTERNAL: "Module internal error.",
            ServiceStatus.ERROR_APP_CONFIG: "App configuration error.",
            ServiceStatus.ERROR_APP_INTERNAL: "App internal error.",
            ServiceStatus.ERROR_UNKNOWN: "Unknown error.",
        }
        error_description = error_status_description.get(
            error_status, "Unknown error status."
        )
        frame = cls.black()
        draw = ImageDraw.Draw(frame)

        lines = []
        words = error_description.split()
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=cls.font)
            text_width = bbox[2] - bbox[0]

            if text_width <= cls.led_cols - 4:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        line_height = 6
        total_height = len(lines) * line_height
        start_y = max(2, (cls.led_rows - total_height) // 2)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=cls.font)
            text_width = bbox[2] - bbox[0]
            x = (cls.led_cols - text_width) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, fill=RED, font=cls.font)

        draw.rectangle((0, 0, cls.led_cols - 1, cls.led_rows - 1), outline=RED, width=1)
        return frame

    @classmethod
    def turn_frame(cls, app_name: str, missing_orientation: str) -> Image:
        """
        Generate a frame telling the user to turn the carousel for missing content.
        """
        frame = cls.black()
        draw = ImageDraw.Draw(frame)

        title = f"{app_name}"
        message = f"No {missing_orientation} content. Turn carousel."

        draw.text((2, 2), title, fill=RED, font=cls.font)

        bbox = draw.textbbox((0, 0), message, font=cls.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = max(0, (cls.led_cols - text_width) // 2)
        y = max(0, (cls.led_rows - text_height) // 2)

        draw.text((x, y), message, fill=RED, font=cls.font)
        draw.rectangle((0, 0, cls.led_cols - 1, cls.led_rows - 1), outline=RED, width=1)
        return frame
