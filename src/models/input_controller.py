
from abc import ABC, abstractmethod
from typing import Optional
import asyncio

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
