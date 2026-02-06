import asyncio
import time
from hardware.display_controller import DisplayController

from loguru import logger

from display.custom_frames import CustomFrames


class Animations:
    display_controller: DisplayController

    def __init__(self) -> None:
        self.display_controller = DisplayController()
        self.matrix = self.display_controller.matrix

    async def loading_animation(self, duration_in_seconds: int = 4) -> None:
        """
        Displays a loading animation on the matrix (async non-blocking).
        Uses asyncio.sleep instead of time.sleep.
        :param duration_in_seconds: Duration of the loading animation in seconds (default is 4).
        """
        if duration_in_seconds <= 0:
            logger.warning("Duration for loading animation must be positive. Skipped.")
            return
        logger.debug("Starting loading animation.")

        start_time = time.time()
        last_update_time = start_time
        update_interval = 0.05

        while True:
            current_time = time.time()
            elapsed = current_time - start_time

            if elapsed >= duration_in_seconds:
                break

            if current_time - last_update_time >= update_interval:
                percentage = min(100, int((elapsed / duration_in_seconds) * 100))
                frame = CustomFrames.loading(percentage)
                if frame is None:
                    logger.error(
                        "CustomFrames.loading() returned None. Ensure CustomFrames.init() was called."
                    )
                    break
                self.matrix.SetImage(frame)
                last_update_time = current_time

            await asyncio.sleep(0.001)

        final_frame = CustomFrames.loading(100)
        if final_frame is not None:
            self.matrix.SetImage(final_frame)

        logger.debug("Loading animation completed.")

        black_frame = CustomFrames.black()
        if black_frame is not None:
            self.matrix.SetImage(black_frame)

        logger.debug("Display cleared after loading animation.")
