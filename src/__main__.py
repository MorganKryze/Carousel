import argparse
import cProfile
import pstats
import time

from loguru import logger
from PIL import Image

from core.app_manager import AppManager
from io.display_controller import DisplayController
from io.input_controller import InputController
from core.system_state import SystemState
from core.config import Configuration
from display.custom_frames import CustomFrames
from display.animations import Animations
from core.logs import Logs
from core.path import PathTo
from enums.encoder_input import EncoderInput
from models.application import Application


@logger.catch
def __main__() -> None:
    parser = argparse.ArgumentParser(description="Carousel LED matrix controller")
    parser.add_argument("--debug", action="store_true", help="Run with debug console")
    parser.add_argument("--emulator", action="store_true", help="Run in emulator mode")
    parser.add_argument("--profile", action="store_true", help="Enable profiling")
    args = parser.parse_args()

    PathTo.set_base_directory()
    PathTo.add_library_to_path()

    file_level = "DEBUG"
    console_level = "DEBUG" if args.debug else "WARNING"

    Logs.start(file_level=file_level, console_level=console_level)

    Configuration.load()

    # Initialize Systems
    state = SystemState()
    input_controller = InputController()
    display = DisplayController(use_emulator=args.emulator)

    # Animations
    animations = Animations()
    animations.loading_animation()

    AppManager.init_apps()

    # TODO: remove this when webserver is implemented with new config and workflow
    # server = WebServer()
    # TODO: port should be configurable
    # server.start(port=9000, debug=args.debug)

    profiler = None
    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        logger.info("Profiling enabled.")

    previous_frame: Image = CustomFrames.black()
    previous_frame_bytes = previous_frame.tobytes()
    next_tick = time.time()
    logger.info("Entering main loop.")
    try:
        while True:
            # TODO: remove this check when webserver is implemented with new config and workflow
            if False:
                # if server.is_user_connected():
                display.matrix.SetImage(CustomFrames.black())
            else:
                if not state.encoder_queue.empty():
                    state.encoder_state += state.encoder_queue.get()

                if state.has_encoder_increased():
                    state.encoder_input = EncoderInput.INCREASE_CLOCKWISE
                    state.reset_encoder_state()
                elif state.has_encoder_decreased():
                    state.encoder_input = EncoderInput.DECREASE_COUNTERCLOCKWISE
                    state.reset_encoder_state()

                current_app: Application = AppManager.get_current_app()
                generated_frame: Image = current_app.generate(
                    state.tilt_state, state.encoder_input
                )

                display_frame = (
                    generated_frame if state.is_display_on else CustomFrames.black()
                )
                if display_frame.mode != "RGB":
                    display_frame = display_frame.convert("RGB")

                frame_bytes = display_frame.tobytes()

                if frame_bytes != previous_frame_bytes:
                    previous_frame = display_frame
                    previous_frame_bytes = frame_bytes
                    display.matrix.SetImage(display_frame)

                state.reset_encoder_input_status()

            next_tick += display.refresh_rate
            sleep_time = next_tick - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Program stopped by user.")
        display.matrix.SetImage(CustomFrames.black())

        input_controller.cleanup()
        display.cleanup()

        if profiler:
            profiler.disable()
            stats = pstats.Stats(profiler).sort_stats("cumtime")
            stats.print_stats(20)
            logger.info("Profiling stats printed.")
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    __main__()
