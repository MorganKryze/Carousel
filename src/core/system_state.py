import queue
from typing import Optional

from loguru import logger

from enums.encoder_input import EncoderInput
from enums.tilt_input import TiltState


class SystemState:
    """
    Singleton class to manage the global state of the system.
    """
    _instance: Optional["SystemState"] = None

    BRIGHTNESS_MIN: int = 0
    BRIGHTNESS_MAX: int = 100
    BRIGHTNESS_STEP: int = 5

    def __new__(cls) -> "SystemState":
        if cls._instance is None:
            cls._instance = super(SystemState, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize default values."""
        self.brightness: int = 100
        self.is_display_on: bool = True
        self.encoder_queue: queue.Queue = queue.Queue()
        self.encoder_state: int = 0
        self.encoder_rotation_this_frame: int = 0  # Rotation change in current frame
        self.tilt_state: TiltState = TiltState.HORIZONTAL
        self.encoder_input: EncoderInput = EncoderInput.NOTHING

    def reset_encoder_state(self) -> None:
        """Resets the encoder state to 0."""
        self.encoder_state = 0

    def reset_encoder_input_status(self) -> None:
        """Resets the encoder input status to NOTHING."""
        self.encoder_input = EncoderInput.NOTHING

    def has_encoder_increased(self) -> bool:
        """Checks if the encoder has increased."""
        return self.encoder_state > 0

    def has_encoder_decreased(self) -> bool:
        """Checks if the encoder has decreased."""
        return self.encoder_state < 0

    def has_encoder_rotated(self) -> bool:
        """Checks if the encoder was rotated this frame."""
        return self.encoder_rotation_this_frame != 0

    async def update_tilt_state(self, new_state: TiltState) -> None:
        """
        Update the tilt state (callback for input controllers).

        Args:
            new_state: The new tilt state (HORIZONTAL or VERTICAL)
        """
        self.tilt_state = new_state
        logger.debug(f"Tilt state updated to: {new_state.name}")

    async def update_encoder_value(self, direction: int) -> None:
        """
        Update the encoder state based on rotation direction (callback for input controllers).

        Args:
            direction: 1 for clockwise, -1 for counter-clockwise
        """
        self.encoder_state += direction
        self.encoder_queue.put(direction)
        logger.debug(f"Encoder rotated: {direction} (state: {self.encoder_state})")

    async def update_encoder_input_status(self, input_status: EncoderInput) -> None:
        """
        Update the encoder input status (callback for input controllers).

        Args:
            input_status: The encoder input status (CLICK, LONG_PRESS, etc.)
        """
        self.encoder_input = input_status
        logger.debug(f"Encoder input: {input_status.name}")
