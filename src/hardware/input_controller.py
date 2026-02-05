import asyncio
import threading
import time
from typing import Optional

from gpiozero import Button, RotaryEncoder
from gpiozero.pins.pigpio import PiGPIOFactory
from loguru import logger

from core.config import Configuration
from core.system_state import SystemState
from enums.encoder_input import EncoderInput
from enums.tilt_input import TiltState


class InputController:
    """
    Manages GPIO inputs (Encoder, Buttons, Tilt Switch).
    No longer a singleton - configuration injected via constructor.
    """

    FIRST_GPIO_PIN: int = 0
    LAST_GPIO_PIN: int = 27
    HOLD_TIME: float = 1.0
    DOUBLE_PRESS_TIME: float = 0.3
    TRIPLE_PRESS_TIME: float = 0.3
    SLEEP_INTERVAL: float = 0.1

    def __init__(self, config: Configuration):
        """
        Initialize input controller with dependency injection.

        :param config: Configuration instance for accessing GPIO settings.
        """
        self._config = config
        self._state: SystemState = SystemState()
        self.factory: PiGPIOFactory = PiGPIOFactory()

        self.encoder_clk: int = 0
        self.encoder_dt: int = 0
        self.encoder_sw: int = 0
        self.tilt_switch_pin: int = 0
        self.tilt_switch_bounce_time: float = 0.0

        self.encoder: Optional[RotaryEncoder] = None
        self.encoder_button: Optional[Button] = None
        self.tilt_switch_button: Optional[Button] = None

        self._button_press_task: Optional[asyncio.Task] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        self._cleanup_gpio()

        try:
            self._init_encoder()
            self._init_tilt_switch()
            logger.debug("Input systems initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Input components: {e}")
            self._cleanup_gpio()
            self._config.critical_exit(
                f"Failed to initialize GPIO components: {e}. "
                "Please ensure no other processes are using the GPIO pins and try running with sudo."
            )

    def _cleanup_gpio(self) -> None:
        """Cleanup GPIO resources to prevent conflicts."""
        try:
            if hasattr(self, "encoder") and self.encoder:
                self.encoder.close()
                logger.debug("Encoder cleaned up.")
        except Exception as e:
            logger.warning(f"Error cleaning up encoder: {e}")

        try:
            if hasattr(self, "encoder_button") and self.encoder_button:
                self.encoder_button.close()
                logger.debug("Encoder button cleaned up.")
        except Exception as e:
            logger.warning(f"Error cleaning up encoder button: {e}")

        try:
            if hasattr(self, "tilt_switch_button") and self.tilt_switch_button:
                self.tilt_switch_button.close()
                logger.debug("Tilt switch button cleaned up.")
        except Exception as e:
            logger.warning(f"Error cleaning up tilt switch button: {e}")

    def _validate_gpio_pin(self, pin: int, name: str) -> None:
        """Validates GPIO pin is within valid range."""
        if pin < self.FIRST_GPIO_PIN or pin > self.LAST_GPIO_PIN:
            self._config.critical_exit(
                f"System.{name} must be between {self.FIRST_GPIO_PIN} and {self.LAST_GPIO_PIN}."
            )

    def _init_encoder(self) -> None:
        """Initializes the encoder settings."""
        self.encoder_clk = self._config.get(
            "System", "Encoder", "gpio_clk", required=True
        )
        self._validate_gpio_pin(self.encoder_clk, "Encoder.gpio_clk")

        self.encoder_dt = self._config.get(
            "System", "Encoder", "gpio_dt", required=True
        )
        self._validate_gpio_pin(self.encoder_dt, "Encoder.gpio_dt")

        try:
            self.encoder = RotaryEncoder(
                self.encoder_clk,
                self.encoder_dt,
                pin_factory=self.factory,
            )
            self.encoder.when_rotated_clockwise = (
                lambda enc: self._rotate_clockwise_callback(enc)
            )
            self.encoder.when_rotated_counter_clockwise = (
                lambda enc: self._rotate_counter_clockwise_callback(enc)
            )
            logger.info("Encoder rotation initialized.")
        except RuntimeError as e:
            if "Failed to add edge detection" in str(e):
                raise RuntimeError(
                    f"GPIO pins {self.encoder_clk} or {self.encoder_dt} are already in use or unavailable."
                ) from e
            raise

        self.encoder_sw = self._config.get(
            "System", "Encoder", "gpio_sw", required=True
        )
        self._validate_gpio_pin(self.encoder_sw, "Encoder.gpio_sw")

        try:
            self.encoder_button = Button(
                self.encoder_sw,
                pull_up=True,
                bounce_time=0.1,
                pin_factory=self.factory,
            )
            self.encoder_button.when_pressed = (
                lambda button: self._encoder_button_callback(button)
            )
            logger.info("Encoder button initialized.")
        except RuntimeError as e:
            if "Failed to add edge detection" in str(e):
                raise RuntimeError(
                    f"GPIO pin {self.encoder_sw} is already in use or unavailable."
                ) from e
            raise

    def _init_tilt_switch(self) -> None:
        """Initializes the tilt switch settings."""
        self.tilt_switch_pin = self._config.get(
            "System", "Tilt-switch", "gpio", required=True
        )
        self._validate_gpio_pin(self.tilt_switch_pin, "Tilt-switch.gpio")

        self.tilt_switch_bounce_time = self._config.get(
            "System", "Tilt-switch", "bounce_time", required=True
        )
        if self.tilt_switch_bounce_time < 0:
            self._config.critical_exit(
                "System.Tilt-switch.bounce_time must be a non-negative number."
            )

        try:
            self.tilt_switch_button = Button(
                self.tilt_switch_pin,
                pull_up=True,
                bounce_time=self.tilt_switch_bounce_time,
                pin_factory=self.factory,
            )
            self._state.tilt_state = (
                TiltState.HORIZONTAL
                if self.tilt_switch_button.is_pressed
                else TiltState.VERTICAL
            )

            self.tilt_switch_button.when_pressed = lambda button: self._tilt_callback(
                button
            )
            self.tilt_switch_button.when_released = lambda button: self._tilt_callback(
                button
            )
            logger.debug("Tilt switch button initialized.")
        except RuntimeError as e:
            if "Failed to add edge detection" in str(e):
                raise RuntimeError(
                    f"GPIO pin {self.tilt_switch_pin} is already in use or unavailable."
                ) from e
            raise

    def _rotate_clockwise_callback(self, encoder: RotaryEncoder) -> None:
        logger.debug("Rotated clockwise: (+).")
        self._state.encoder_queue.put_nowait(1)
        encoder.value = 0

    def _rotate_counter_clockwise_callback(self, encoder: RotaryEncoder) -> None:
        logger.debug("Rotated counter-clockwise: (-).")
        self._state.encoder_queue.put_nowait(-1)
        encoder.value = 0

    def _tilt_callback(self, tilt_switch: Button) -> None:
        current_tilt_state = (
            TiltState.HORIZONTAL if tilt_switch.is_pressed else TiltState.VERTICAL
        )

        if current_tilt_state != self._state.tilt_state:
            self._state.tilt_state = current_tilt_state
            logger.debug(
                f"Orientation changed to {self._state.tilt_state.name.lower()}."
            )

    def _encoder_button_callback(self, enc_button: Button) -> None:
        """Initiate async button detection when pressed."""
        if self._button_press_task and not self._button_press_task.done():
            self._button_press_task.cancel()

        # Schedule task on the correct event loop
        if self._event_loop and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._detect_button_press_async(enc_button), self._event_loop
            )
        else:
            logger.warning(
                "AsyncIO event loop not available. Falling back to sync detection."
            )
            # Run sync detection in a separate thread to avoid blocking GPIO
            threading.Thread(
                target=self._detect_button_press_sync, args=(enc_button,), daemon=True
            ).start()

    async def _detect_button_press_async(self, enc_button: Button) -> None:
        """Async button press detection - non-blocking."""
        try:
            start_time = time.time()

            while enc_button.is_active and (time.time() - start_time < self.HOLD_TIME):
                await asyncio.sleep(0.01)

            if time.time() - start_time >= self.HOLD_TIME:
                logger.debug("Long press detected (5).")
                self._state.encoder_input = EncoderInput.LONG_PRESS
            else:
                start_time = time.time()
                while time.time() - start_time <= self.DOUBLE_PRESS_TIME:
                    await asyncio.sleep(0.01)
                    if enc_button.is_pressed:
                        await asyncio.sleep(0.01)
                        triple_start = time.time()
                        while time.time() - triple_start <= self.TRIPLE_PRESS_TIME:
                            await asyncio.sleep(0.01)
                            if enc_button.is_pressed:
                                logger.debug("Triple press detected (3).")
                                self._state.encoder_input = EncoderInput.TRIPLE_PRESS
                                return

                        logger.debug("Double press detected (2).")
                        self._state.encoder_input = EncoderInput.DOUBLE_PRESS
                        return

                logger.debug("Single press detected (1).")
                self._state.encoder_input = EncoderInput.SINGLE_PRESS

        except asyncio.CancelledError:
            logger.debug("Button press detection cancelled.")

    def _detect_button_press_sync(self, enc_button: Button) -> None:
        """Fallback sync button press detection."""
        start_time = time.time()
        time_diff = 0

        while enc_button.is_active and (time_diff < self.HOLD_TIME):
            time_diff = time.time() - start_time

        if time_diff >= self.HOLD_TIME:
            logger.debug("Long press detected (5).")
            self._state.encoder_input = EncoderInput.LONG_PRESS
        else:
            enc_button.when_pressed = None
            start_time = time.time()
            while time.time() - start_time <= self.DOUBLE_PRESS_TIME:
                time.sleep(self.SLEEP_INTERVAL)
                if enc_button.is_pressed:
                    time.sleep(self.SLEEP_INTERVAL)
                    new_start_time = time.time()
                    while time.time() - new_start_time <= self.TRIPLE_PRESS_TIME:
                        time.sleep(self.SLEEP_INTERVAL)
                        if enc_button.is_pressed:
                            logger.debug("Triple press detected (3).")
                            self._state.encoder_input = EncoderInput.TRIPLE_PRESS
                            enc_button.when_pressed = (
                                lambda button: self._encoder_button_callback(button)
                            )
                            return
                        logger.debug("Double press detected (2).")
                        self._state.encoder_input = EncoderInput.DOUBLE_PRESS
                        enc_button.when_pressed = (
                            lambda button: self._encoder_button_callback(button)
                        )
                        return
            logger.debug("Single press detected (1).")
            self._state.encoder_input = EncoderInput.SINGLE_PRESS
            enc_button.when_pressed = lambda button: self._encoder_button_callback(
                button
            )

    def cleanup(self) -> None:
        """Public method to cleanup resources on shutdown."""
        logger.info("Cleaning up InputController resources...")

        if self._button_press_task and not self._button_press_task.done():
            self._button_press_task.cancel()

        self._cleanup_gpio()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Register the asyncio event loop for cross-thread task scheduling.
        Must be called after asyncio.run() starts but before GPIO callbacks fire.
        """
        self._event_loop = loop
        logger.debug("Event loop registered with InputController.")
