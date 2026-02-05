import time

from loguru import logger

from display.custom_frames import CustomFrames
from io.display_controller import DisplayController


class Animations:
    display_controller: DisplayController

    def __init__(self) -> None:
        self.display_controller = DisplayController()
        self.matrix = self.display_controller.matrix

    def loading_animation(self, duration_in_seconds: int = 4) -> None:
        """
        Displays a loading animation on the matrix.
        :param duration_in_seconds: Duration of the loading animation in seconds (default is 4).
        """
        if duration_in_seconds <= 0:
            logger.warning("Duration for loading animation must be positive. Skipped.")
            return
        logger.debug("Starting loading animation.")
        start_time = time.time()
        while time.time() - start_time < duration_in_seconds:
            elapsed = time.time() - start_time
            percentage = min(100, int((elapsed / duration_in_seconds) * 100))
            frame = CustomFrames.loading(percentage)
            if frame is None:
                logger.error(
                    "CustomFrames.loading() returned None. Ensure CustomFrames.init() was called."
                )
                break
            self.matrix.SetImage(frame)
            time.sleep(0.1)
        final_frame = CustomFrames.loading(100)
        if final_frame is not None:
            self.matrix.SetImage(final_frame)
            time.sleep(0.5)
        logger.debug("Loading animation completed.")
        black_frame = CustomFrames.black()
        if black_frame is not None:
            self.matrix.SetImage(black_frame)
            time.sleep(0.5)
        logger.debug("Display cleared after loading animation.")
