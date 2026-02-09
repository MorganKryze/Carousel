import asyncio
import time
from typing import Optional

from loguru import logger

from enums.encoder_input import EncoderInput
from enums.tilt_input import TiltState
from models.input_controller import InputController


class KeyboardInputController(InputController):
    """Keyboard-based input controller for desktop development."""

    # Press detection timing constants (in seconds)
    LONG_PRESS_THRESHOLD = 0.5  # Hold for 0.5s = long press
    DOUBLE_PRESS_WINDOW = 0.3  # Second press within 0.3s = double press

    def __init__(self, reverse_rotation: bool = False):
        super().__init__()
        logger.info("Initializing keyboard input controller...")

        try:
            from pynput import keyboard  # type: ignore
        except ImportError:
            logger.error("pynput not installed. Install with: pip install pynput")
            raise

        self.current_tilt = TiltState.HORIZONTAL

        self.button_press_start_time: Optional[float] = None
        self.button_press_count = 0
        self.last_press_time: Optional[float] = None
        self.pending_press_task: Optional[asyncio.Task] = None

        if not isinstance(reverse_rotation, bool):
            logger.error(
                f"Invalid reverse_rotation: {reverse_rotation}. Must be a boolean."
            )
            raise ValueError("Encoder reverse_rotation must be a boolean")
        self.encoder_direction_multiplier = -1 if reverse_rotation else 1

        self.listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self.listener.start()
        logger.info("Keyboard input controller initialized. Controls:")
        logger.info("  Space: Toggle tilt (horizontal/vertical)")
        logger.info("  Left Arrow: Rotate encoder CCW")
        logger.info("  Right Arrow: Rotate encoder CW")
        logger.info("  Down Arrow: Single press (quick tap)")
        logger.info("  Down Arrow x2: Double press (two quick taps)")
        logger.info("  Down Arrow (hold): Long press (hold for 0.5s)")

    def _on_key_press(self, key) -> None:
        """Handle key press events."""
        try:
            from pynput import keyboard  # type: ignore

            if key == keyboard.Key.space:
                new_state = (
                    TiltState.VERTICAL
                    if self.current_tilt == TiltState.HORIZONTAL
                    else TiltState.HORIZONTAL
                )
                self.current_tilt = new_state
                if self.on_tilt_change_callback and self.event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_tilt_change_callback(new_state), self.event_loop
                    )

            elif key == keyboard.Key.left:
                if self.on_encoder_change_callback and self.event_loop:
                    direction = -1 * self.encoder_direction_multiplier
                    asyncio.run_coroutine_threadsafe(
                        self.on_encoder_change_callback(direction), self.event_loop
                    )
                    logger.debug("Encoder: CCW")

            elif key == keyboard.Key.right:
                if self.on_encoder_change_callback and self.event_loop:
                    direction = 1 * self.encoder_direction_multiplier
                    asyncio.run_coroutine_threadsafe(
                        self.on_encoder_change_callback(direction), self.event_loop
                    )
                    logger.debug("Encoder: CW")

            elif key == keyboard.Key.down:
                if self.button_press_start_time is None:
                    self.button_press_start_time = time.time()

        except Exception as e:
            logger.error(f"Error handling key press: {e}", exc_info=True)

    def _on_key_release(self, key) -> None:
        """Handle key release events for button press detection."""
        try:
            from pynput import keyboard  # type: ignore

            if key == keyboard.Key.down and self.button_press_start_time is not None:
                press_duration = time.time() - self.button_press_start_time
                self.button_press_start_time = None

                if press_duration >= self.LONG_PRESS_THRESHOLD:
                    self._trigger_press(EncoderInput.LONG_PRESS)
                else:
                    self._handle_quick_press()

        except Exception as e:
            logger.error(f"Error handling key release: {e}", exc_info=True)

    def _handle_quick_press(self) -> None:
        """Handle quick button presses (single/double/triple)."""
        current_time = time.time()

        if (
            self.last_press_time
            and (current_time - self.last_press_time) < self.DOUBLE_PRESS_WINDOW
        ):
            self.button_press_count += 1

            if self.pending_press_task and not self.pending_press_task.done():
                self.pending_press_task.cancel()
        else:
            self.button_press_count = 1

        self.last_press_time = current_time

        if self.event_loop:
            self.pending_press_task = asyncio.run_coroutine_threadsafe(
                self._finalize_press_detection(), self.event_loop
            )

    async def _finalize_press_detection(self) -> None:
        """Wait for double-press window to expire, then trigger the appropriate press."""
        try:
            await asyncio.sleep(self.DOUBLE_PRESS_WINDOW)

            if self.button_press_count == 1:
                self._trigger_press(EncoderInput.SINGLE_PRESS)
            elif self.button_press_count == 2:
                self._trigger_press(EncoderInput.DOUBLE_PRESS)
            elif self.button_press_count >= 3:
                self._trigger_press(EncoderInput.TRIPLE_PRESS)

            self.button_press_count = 0

        except asyncio.CancelledError:
            # Task was cancelled (another press came in)
            pass
        except Exception as e:
            logger.error(f"Error in press detection: {e}", exc_info=True)

    def _trigger_press(self, press_type: EncoderInput) -> None:
        """Trigger the encoder button callback with the detected press type."""
        if self.on_encoder_button_callback and self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self.on_encoder_button_callback(press_type),
                self.event_loop,
            )
            logger.debug(f"Encoder: {press_type.name}")

    def cleanup(self) -> None:
        """Cleanup keyboard listener."""
        logger.info("Cleaning up keyboard input controller...")

        if self.pending_press_task and not self.pending_press_task.done():
            self.pending_press_task.cancel()

        if hasattr(self, "listener"):
            self.listener.stop()
