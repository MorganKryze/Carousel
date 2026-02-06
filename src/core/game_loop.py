import asyncio
import signal
import time

from loguru import logger
from PIL import Image

from core.app_manager import AppManager
from core.system_context import SystemContext
from display.custom_frames import CustomFrames
from models.application import Application


class GameLoop:
    """
    Main game loop coordinating singleton components.
    """

    def __init__(self, target_fps: int = 10, use_emulator: bool = False):
        self.target_fps = target_fps
        self.time_per_frame = 1.0 / target_fps
        self.last_frame_time = time.time()
        self.running = True

        # Initialize singletons in correct order
        self.context = SystemContext(use_emulator=use_emulator)
        
        event_loop = asyncio.get_running_loop()
        self.context.input_controller.set_event_loop(event_loop)

        self.app_manager = AppManager()
        self.app_manager.init_apps()

        self.previous_frame: Image = CustomFrames.black()
        self.previous_frame_bytes = self.previous_frame.tobytes()

        logger.info("Game loop initialized successfully.")

    def setup_signal_handlers(self, render_task: asyncio.Task) -> None:
        """Register signal handlers for graceful shutdown."""

        def shutdown_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self.running = False
            render_task.cancel()

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    async def render_loop(self) -> None:
        """Main render loop executing at fixed framerate."""
        logger.info("Starting render loop...")

        try:
            while self.running:
                current_time = time.time()
                elapsed = current_time - self.last_frame_time

                if elapsed >= self.time_per_frame:
                    self.last_frame_time = current_time
                    self._process_frame()

                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logger.info("Render loop cancelled.")
        except Exception as e:
            logger.error(f"Error in render loop: {e}", exc_info=True)
            raise

    def _process_frame(self) -> None:
        """Process a single frame: handle inputs, generate image, update display."""
        state = self.context.state

        # Accumulate all encoder changes from this frame
        total_encoder_change = 0
        while not state.encoder_queue.empty():
            total_encoder_change += state.encoder_queue.get_nowait()

        # Apply accumulated change only once per frame
        if total_encoder_change > 0:
            self.app_manager.switch_next_app()
        elif total_encoder_change < 0:
            self.app_manager.switch_prev_app()

        current_app: Application = self.app_manager.get_current_app()
        generated_frame: Image = current_app.generate(
            state.tilt_state, state.encoder_input
        )

        display_frame = generated_frame if state.is_display_on else CustomFrames.black()
        if display_frame.mode != "RGB":
            display_frame = display_frame.convert("RGB")

        frame_bytes = display_frame.tobytes()

        if frame_bytes != self.previous_frame_bytes:
            self.previous_frame = display_frame
            self.previous_frame_bytes = frame_bytes
            self.context.display.matrix.SetImage(display_frame)

        state.reset_encoder_input_status()

    def cleanup(self) -> None:
        """Release all hardware resources."""
        logger.info("Cleaning up resources...")

        if SystemContext.is_initialized():
            if self.context.display:
                self.context.display.matrix.SetImage(CustomFrames.black())
                self.context.display.cleanup()

            if self.context.input_controller:
                self.context.input_controller.cleanup()

        logger.info("Cleanup complete.")
