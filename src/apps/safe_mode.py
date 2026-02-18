"""Safe Mode application - displays critical error information and recovery instructions."""

from typing import Callable, Dict

from loguru import logger
from PIL import Image

from core.system_context import SystemContext
from display.custom_frames import CustomFrames
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState


class SafeMode:
    """
    Special application that runs when the system enters safe mode.

    Unlike normal apps, this does not rely on module/app initialization and
    only renders a minimal recovery instruction frame.
    """

    def __init__(self, context: SystemContext, callbacks: Dict[str, Callable]):
        """
        Initialize SafeMode app.

        :param context: Singleton SystemContext instance.
        :param callbacks: Dictionary of callback functions (unused in safe mode).
        """
        self.context = context
        self.callbacks = callbacks
        self.status: ServiceStatus = ServiceStatus.RUNNING

        self.enabled = True
        self.name = "Safe Mode"
        self.description = "Critical error recovery mode"
        self.provides_horizontal_content = True
        self.provides_vertical_content = True

        logger.info("SafeMode app initialized")

    def generate(self, tilt_state: TiltState, encoder_input: EncoderInput) -> Image:
        """
        Generate the safe mode frame with recovery instructions.

        :param tilt_state: Current tilt state (unused in safe mode).
        :param encoder_input: Encoder input (unused in safe mode).
        :return: Safe mode frame.
        """
        return CustomFrames.safe_mode()

    def generate_on_error(self) -> Image:
        """
        Fallback if safe mode frame rendering itself fails.

        :return: Black frame.
        """
        logger.critical("SafeMode app itself encountered an error!")
        return CustomFrames.black()
