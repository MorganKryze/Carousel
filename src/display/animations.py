import asyncio
import time

from loguru import logger

from core.system_context import SystemContext
from display.custom_frames import CustomFrames


class Animations:
    def __init__(self) -> None:
        self.context = SystemContext()

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

        target_fps = self.context.display.target_fps

        start_time = time.time()
        last_update_time = start_time
        update_interval = 1.0 / target_fps

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
                self.context.display.matrix.SetImage(frame)
                last_update_time = current_time

            await asyncio.sleep(0.001)

        final_frame = CustomFrames.loading(100)
        if final_frame is not None:
            self.context.display.matrix.SetImage(final_frame)
        await asyncio.sleep(1)

        logger.debug("Loading animation completed.")

        black_frame = CustomFrames.black()
        if black_frame is not None:
            self.context.display.matrix.SetImage(black_frame)

        logger.debug("Display cleared after loading animation.")
