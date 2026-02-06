import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger

from enums.encoder_input import EncoderInput
from enums.tilt_input import TiltState


class InputController(ABC):
    """Abstract base class for input handling."""

    def __init__(self):
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.on_tilt_change_callback = None
        self.on_encoder_change_callback = None
        self.on_encoder_button_callback = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for async callbacks."""
        self.event_loop = loop

    def set_callbacks(
        self,
        on_tilt_change,
        on_encoder_change,
        on_encoder_button,
    ) -> None:
        """Set callback functions for input events."""
        self.on_tilt_change_callback = on_tilt_change
        self.on_encoder_change_callback = on_encoder_change
        self.on_encoder_button_callback = on_encoder_button

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources."""
        pass


class GPIOInputController(InputController):
    """GPIO-based input controller for Raspberry Pi."""

    def __init__(self, config):
        super().__init__()
        logger.info("Initializing GPIO input controller...")

        try:
            import pigpio  # type: ignore
            from gpiozero import Button
        except ImportError:
            logger.error("GPIO libraries not available. Install pigpio and gpiozero.")
            raise

        # Tilt switch setup
        self.tilt_gpio = config.get("System", "Tilt-switch", "gpio", required=True)
        bounce_time = config.get(
            "System", "Tilt-switch", "bounce_time", default=0.25, required=True
        )
        self.tilt_switch = Button(self.tilt_gpio, bounce_time=bounce_time)
        self.tilt_switch.when_pressed = self._on_tilt_change
        self.tilt_switch.when_released = self._on_tilt_change

        # Encoder setup
        self.encoder_gpio_clk = config.get(
            "System", "Encoder", "gpio_clk", required=True
        )
        self.encoder_gpio_dt = config.get("System", "Encoder", "gpio_dt", required=True)
        self.encoder_gpio_sw = config.get("System", "Encoder", "gpio_sw", required=True)

        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Failed to connect to pigpio daemon")

        self.encoder_button = Button(self.encoder_gpio_sw)
        self.encoder_button.when_pressed = self._on_encoder_button_press

        self.pi.set_mode(self.encoder_gpio_clk, pigpio.INPUT)
        self.pi.set_mode(self.encoder_gpio_dt, pigpio.INPUT)
        self.pi.set_pull_up_down(self.encoder_gpio_clk, pigpio.PUD_UP)
        self.pi.set_pull_up_down(self.encoder_gpio_dt, pigpio.PUD_UP)

        self.encoder_callback = self.pi.callback(
            self.encoder_gpio_clk, pigpio.EITHER_EDGE, self._encoder_pulse
        )

        logger.info("GPIO input controller initialized successfully.")

    def _on_tilt_change(self) -> None:
        """Handle tilt switch state change."""
        if self.on_tilt_change_callback and self.event_loop:
            new_state = (
                TiltState.HORIZONTAL
                if self.tilt_switch.is_pressed
                else TiltState.VERTICAL
            )
            asyncio.run_coroutine_threadsafe(
                self.on_tilt_change_callback(new_state), self.event_loop
            )

    def _encoder_pulse(self, gpio, level, tick) -> None:
        """Handle encoder rotation."""
        if self.on_encoder_change_callback and self.event_loop:
            dt_state = self.pi.read(self.encoder_gpio_dt)
            direction = 1 if dt_state == 0 else -1
            asyncio.run_coroutine_threadsafe(
                self.on_encoder_change_callback(direction), self.event_loop
            )

    def _on_encoder_button_press(self) -> None:
        """Handle encoder button press."""
        if self.on_encoder_button_callback and self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self.on_encoder_button_callback(EncoderInput.SINGLE_PRESS),
                self.event_loop,
            )

    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        logger.info("Cleaning up GPIO input controller...")
        if hasattr(self, "encoder_callback"):
            self.encoder_callback.cancel()
        if hasattr(self, "pi"):
            self.pi.stop()
        if hasattr(self, "tilt_switch"):
            self.tilt_switch.close()
        if hasattr(self, "encoder_button"):
            self.encoder_button.close()


class KeyboardInputController(InputController):
    """Keyboard-based input controller for desktop development."""

    # Press detection timing constants (in seconds)
    LONG_PRESS_THRESHOLD = 0.5  # Hold for 0.5s = long press
    DOUBLE_PRESS_WINDOW = 0.3  # Second press within 0.3s = double press

    def __init__(self):
        super().__init__()
        logger.info("Initializing keyboard input controller...")

        try:
            from pynput import keyboard  # type: ignore
        except ImportError:
            logger.error("pynput not installed. Install with: pip install pynput")
            raise

        self.current_tilt = TiltState.HORIZONTAL

        # Button press detection state
        self.button_press_start_time: Optional[float] = None
        self.button_press_count = 0
        self.last_press_time: Optional[float] = None
        self.pending_press_task: Optional[asyncio.Task] = None

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
                # Toggle tilt
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
                # Encoder rotate counter-clockwise
                if self.on_encoder_change_callback and self.event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_encoder_change_callback(-1), self.event_loop
                    )
                    logger.debug("Encoder: CCW")

            elif key == keyboard.Key.right:
                # Encoder rotate clockwise
                if self.on_encoder_change_callback and self.event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_encoder_change_callback(1), self.event_loop
                    )
                    logger.debug("Encoder: CW")

            elif key == keyboard.Key.down:
                # Start tracking button press
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

                # Check if it's a long press
                if press_duration >= self.LONG_PRESS_THRESHOLD:
                    self._trigger_press(EncoderInput.LONG_PRESS)
                else:
                    # It's a quick press - check for double/triple press
                    self._handle_quick_press()

        except Exception as e:
            logger.error(f"Error handling key release: {e}", exc_info=True)

    def _handle_quick_press(self) -> None:
        """Handle quick button presses (single/double/triple)."""
        current_time = time.time()

        # Check if this is part of a multi-press sequence
        if (
            self.last_press_time
            and (current_time - self.last_press_time) < self.DOUBLE_PRESS_WINDOW
        ):
            self.button_press_count += 1

            # Cancel pending single press if it exists
            if self.pending_press_task and not self.pending_press_task.done():
                self.pending_press_task.cancel()
        else:
            # New press sequence
            self.button_press_count = 1

        self.last_press_time = current_time

        # Schedule press detection after the double-press window
        if self.event_loop:
            self.pending_press_task = asyncio.run_coroutine_threadsafe(
                self._finalize_press_detection(), self.event_loop
            )

    async def _finalize_press_detection(self) -> None:
        """Wait for double-press window to expire, then trigger the appropriate press."""
        try:
            await asyncio.sleep(self.DOUBLE_PRESS_WINDOW)

            # Determine press type based on count
            if self.button_press_count == 1:
                self._trigger_press(EncoderInput.SINGLE_PRESS)
            elif self.button_press_count == 2:
                self._trigger_press(EncoderInput.DOUBLE_PRESS)
            elif self.button_press_count >= 3:
                self._trigger_press(EncoderInput.TRIPLE_PRESS)

            # Reset state
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

        # Cancel pending press detection task
        if self.pending_press_task and not self.pending_press_task.done():
            self.pending_press_task.cancel()

        if hasattr(self, "listener"):
            self.listener.stop()
