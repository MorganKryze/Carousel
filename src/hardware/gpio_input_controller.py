import asyncio
import time
from typing import Optional

from loguru import logger

from enums.encoder_input import EncoderInput
from enums.tilt_input import TiltState
from models.input_controller import InputController


class GPIOInputController(InputController):
    """GPIO-based input controller for Raspberry Pi."""

    # Press detection timing constants (in seconds)
    LONG_PRESS_THRESHOLD = 0.5
    DOUBLE_PRESS_WINDOW = 0.3
    
    # GPIO pin range validation
    FIRST_GPIO_PIN = 0
    LAST_GPIO_PIN = 27

    def __init__(self, config):
        super().__init__()
        logger.info("Initializing GPIO input controller...")

        try:
            from gpiozero import Button, RotaryEncoder
            from gpiozero.pins.pigpio import PiGPIOFactory
        except ImportError:
            logger.error("GPIO libraries not available. Install pigpio and gpiozero.")
            raise

        self.factory = PiGPIOFactory()

        self.button_press_start_time: Optional[float] = None
        self.button_press_count = 0
        self.last_press_time: Optional[float] = None
        self.pending_press_task: Optional[asyncio.Task] = None

        self.tilt_gpio = config.get("System", "Tilt-switch", "gpio", required=True)
        self._validate_gpio_pin(self.tilt_gpio, "Tilt-switch.gpio")
        
        bounce_time = config.get(
            "System", "Tilt-switch", "bounce_time", default=0.25, required=True
        )
        if bounce_time < 0:
            logger.error(f"Invalid bounce_time: {bounce_time}. Must be non-negative.")
            raise ValueError("Tilt-switch bounce_time must be non-negative")
            
        self.tilt_switch = Button(
            self.tilt_gpio,
            pull_up=True,
            bounce_time=bounce_time,
            pin_factory=self.factory,
        )
        self.tilt_switch.when_pressed = self._on_tilt_change
        self.tilt_switch.when_released = self._on_tilt_change

        encoder_gpio_clk = config.get("System", "Encoder", "gpio_clk", required=True)
        self._validate_gpio_pin(encoder_gpio_clk, "Encoder.gpio_clk")
        
        encoder_gpio_dt = config.get("System", "Encoder", "gpio_dt", required=True)
        self._validate_gpio_pin(encoder_gpio_dt, "Encoder.gpio_dt")
        
        encoder_gpio_sw = config.get("System", "Encoder", "gpio_sw", required=True)
        self._validate_gpio_pin(encoder_gpio_sw, "Encoder.gpio_sw")

        self.encoder = RotaryEncoder(
            encoder_gpio_clk,
            encoder_gpio_dt,
            pin_factory=self.factory,
        )
        self.encoder.when_rotated_clockwise = self._on_encoder_clockwise
        self.encoder.when_rotated_counter_clockwise = self._on_encoder_counter_clockwise

        self.encoder_button = Button(
            encoder_gpio_sw,
            pull_up=True,
            bounce_time=0.1,
            pin_factory=self.factory,
        )
        self.encoder_button.when_pressed = self._on_encoder_button_press
        self.encoder_button.when_released = self._on_encoder_button_release

        logger.info("GPIO input controller initialized successfully.")

    def _validate_gpio_pin(self, pin: int, name: str) -> None:
        """Validates GPIO pin is within valid range."""
        if pin < self.FIRST_GPIO_PIN or pin > self.LAST_GPIO_PIN:
            logger.error(
                f"Invalid GPIO pin {pin} for {name}. "
                f"Must be between {self.FIRST_GPIO_PIN} and {self.LAST_GPIO_PIN}."
            )
            raise ValueError(
                f"GPIO pin for {name} must be between {self.FIRST_GPIO_PIN} and {self.LAST_GPIO_PIN}"
            )

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

    def _on_encoder_clockwise(self) -> None:
        """Handle encoder clockwise rotation."""
        if self.on_encoder_change_callback and self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self.on_encoder_change_callback(1), self.event_loop
            )
            self.encoder.value = 0
            logger.debug("Encoder: CW")

    def _on_encoder_counter_clockwise(self) -> None:
        """Handle encoder counter-clockwise rotation."""
        if self.on_encoder_change_callback and self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self.on_encoder_change_callback(-1), self.event_loop
            )
            self.encoder.value = 0
            logger.debug("Encoder: CCW")

    def _on_encoder_button_press(self) -> None:
        """Handle encoder button press (start timing)."""
        if self.button_press_start_time is None:
            self.button_press_start_time = time.time()

    def _on_encoder_button_release(self) -> None:
        """Handle encoder button release (detect press type)."""
        if self.button_press_start_time is None:
            return

        press_duration = time.time() - self.button_press_start_time
        self.button_press_start_time = None

        if press_duration >= self.LONG_PRESS_THRESHOLD:
            self._trigger_press(EncoderInput.LONG_PRESS)
        else:
            self._handle_quick_press()

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
        """Cleanup GPIO resources."""
        logger.info("Cleaning up GPIO input controller...")

        if self.pending_press_task and not self.pending_press_task.done():
            self.pending_press_task.cancel()

        if hasattr(self, "encoder"):
            self.encoder.close()
        if hasattr(self, "encoder_button"):
            self.encoder_button.close()
        if hasattr(self, "tilt_switch"):
            self.tilt_switch.close()

