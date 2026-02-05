import asyncio
import signal
import time
from io.display_controller import DisplayController
from io.input_controller import InputController

from loguru import logger
from PIL import Image

from core.app_manager import AppManager
from core.system_state import SystemState
from display.custom_frames import CustomFrames
from enums.encoder_input import EncoderInput
from models.application import Application


class AsyncGameLoop:
    """
    Main game loop handling:
    - System initialization
    - Frame rendering at fixed FPS
    - Graceful shutdown on signals
    """

    def __init__(self, target_fps: int = 10):
        self.target_fps = target_fps
        self.time_per_frame = 1.0 / target_fps
        self.last_frame_time = time.time()
        self.running = True

        self.state: SystemState = None
        self.input_controller: InputController = None
        self.display: DisplayController = None

        self.previous_frame: Image = CustomFrames.black()
        self.previous_frame_bytes = self.previous_frame.tobytes()

    def initialize_systems(self, use_emulator: bool = False) -> None:
        """
        Initialize all hardware and software systems.
        Called once before the render loop starts.
        """
        logger.info("Initializing systems...")

        self.state = SystemState()
        self.input_controller = InputController()
        self.display = DisplayController(use_emulator=use_emulator)

        event_loop = asyncio.get_running_loop()
        self.input_controller.set_event_loop(event_loop)

        AppManager.init_apps()

        logger.info("Systems initialized successfully.")

    def setup_signal_handlers(self, render_task: asyncio.Task) -> None:
        """
        Register signal handlers for graceful shutdown.
        Handles SIGINT (Ctrl+C) and SIGTERM (systemd/docker stop).
        """

        def shutdown_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self.running = False
            render_task.cancel()

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    async def render_loop(self) -> None:
        """
        Main render loop executing at fixed framerate.
        Processes input events and updates display when frame time elapses.
        """
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
        while not self.state.encoder_queue.empty():
            self.state.encoder_state += self.state.encoder_queue.get_nowait()

        if self.state.has_encoder_increased():
            self.state.encoder_input = EncoderInput.INCREASE_CLOCKWISE
            self.state.reset_encoder_state()
        elif self.state.has_encoder_decreased():
            self.state.encoder_input = EncoderInput.DECREASE_COUNTERCLOCKWISE
            self.state.reset_encoder_state()

        current_app: Application = AppManager.get_current_app()
        generated_frame: Image = current_app.generate(
            self.state.tilt_state, self.state.encoder_input
        )

        display_frame = (
            generated_frame if self.state.is_display_on else CustomFrames.black()
        )
        if display_frame.mode != "RGB":
            display_frame = display_frame.convert("RGB")

        frame_bytes = display_frame.tobytes()

        if frame_bytes != self.previous_frame_bytes:
            self.previous_frame = display_frame
            self.previous_frame_bytes = frame_bytes
            self.display.matrix.SetImage(display_frame)

        self.state.reset_encoder_input_status()

    def cleanup(self) -> None:
        """
        Release all hardware resources.
        Called during shutdown to ensure clean exit.
        """
        logger.info("Cleaning up resources...")

        if self.display:
            self.display.matrix.SetImage(CustomFrames.black())
            self.display.cleanup()

        if self.input_controller:
            self.input_controller.cleanup()

        logger.info("Cleanup complete.")
