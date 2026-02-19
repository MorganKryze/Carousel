import asyncio
import signal
import time

from loguru import logger
from PIL import Image

from core.app_manager import AppManager
from core.system_context import SystemContext
from display.custom_frames import CustomFrames
from enums.encoder_input import EncoderInput
from models.application import Application


class GameLoop:
    """
    Main game loop coordinating singleton components.
    """

    _instance: "GameLoop" = None

    def __new__(cls, use_emulator: bool = False) -> "GameLoop":
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(GameLoop, cls).__new__(cls)
            cls._instance._initialize(use_emulator)
        return cls._instance

    def _initialize(self, use_emulator: bool = False) -> None:
        """Initialize game loop state on creation."""
        self.context = SystemContext(use_emulator=use_emulator)

        self.target_fps = self.context.display.target_fps
        self.time_per_frame = 1.0 / self.target_fps
        self.last_frame_time = time.time()
        self.running = True

        event_loop = asyncio.get_running_loop()
        self.context.input_controller.set_event_loop(event_loop)

        self.app_manager = AppManager()
        self.app_manager.init_apps()

        self.previous_frame: Image = CustomFrames.black()
        self.previous_frame_bytes = self.previous_frame.tobytes()

        # Auto-start webserver if in safe mode
        if self.context.config.is_safe_mode():
            logger.warning("SAFE MODE: Auto-starting webserver for recovery")
            self._start_webserver_for_safe_mode()

        logger.info("Game loop initialized successfully.")

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if GameLoop singleton has been initialized."""
        return cls._instance is not None

    def _start_webserver_for_safe_mode(self) -> None:
        """Start webserver in safe mode for user to fix configuration."""
        try:
            from core.webserver import WebServer

            webserver = WebServer()
            webserver.start(port=9000, debug=False)

            logger.info("Webserver started on port 9000 for safe mode recovery")
            logger.info("Access the webserver to fix configuration or rollback")
        except Exception as e:
            logger.error(f"Failed to start webserver in safe mode: {e}")
            logger.error("Manual intervention may be required")

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

        encoder_change_this_frame = 0
        while not state.encoder_queue.empty():
            encoder_change_this_frame += state.encoder_queue.get_nowait()

        state.encoder_rotation_this_frame = encoder_change_this_frame

        if state.encoder_input == EncoderInput.NOTHING:
            if encoder_change_this_frame > 0:
                state.encoder_input = EncoderInput.INCREASE_CLOCKWISE
            elif encoder_change_this_frame < 0:
                state.encoder_input = EncoderInput.DECREASE_COUNTERCLOCKWISE

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
        state.encoder_rotation_this_frame = 0

    def cleanup(self) -> None:
        """Release all hardware resources.

        Critical for Raspberry Pi: Ensures GPIO pins, SPI/I2C buses, and display
        hardware are properly released. This is essential before restart, as the
        new process cannot claim resources still held by the old process.
        """
        logger.info("Cleaning up resources...")

        if SystemContext.is_initialized():
            if self.context.display:
                try:
                    logger.debug("Clearing display to black...")
                    self.context.display.matrix.SetImage(CustomFrames.black())
                except Exception as e:
                    logger.warning(f"Failed to clear display: {e}")

                try:
                    logger.debug("Releasing display controller (SPI/GPIO)...")
                    self.context.display.cleanup()
                except Exception as e:
                    logger.error(f"Failed to cleanup display controller: {e}")

            if self.context.input_controller:
                try:
                    logger.debug("Releasing input controller (GPIO pins)...")
                    self.context.input_controller.cleanup()
                except Exception as e:
                    logger.error(f"Failed to cleanup input controller: {e}")

            if self.context.state:
                try:
                    logger.debug("Clearing system state and queues...")
                    self.context.state.encoder_rotation_this_frame = 0
                    self.context.state.encoder_queue.queue.clear()
                except Exception as e:
                    logger.warning(f"Failed to clear state: {e}")
        logger.info("Cleanup complete.")
