"""Recovery Mode application - displays critical error information and recovery instructions."""

from typing import Callable, Dict

from loguru import logger
from PIL import Image

from core.system_context import SystemContext
from display.custom_frames import CustomFrames
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState


class RecoveryMode:
    """
    Special application that runs when the system enters recovery mode.

    Unlike normal apps, this does not rely on module/app initialization and
    only renders a minimal recovery instruction frame.
    """

    def __init__(self, context: SystemContext, callbacks: Dict[str, Callable]):
        """
        Initialize RecoveryMode app.

        :param context: Singleton SystemContext instance.
        :param callbacks: Dictionary of callback functions (unused in recovery mode).
        """
        self.context = context
        self.callbacks = callbacks
        self.status: ServiceStatus = ServiceStatus.RUNNING

        self.enabled = True
        self.name = "Recovery Mode"
        self.description = "Critical error recovery mode"
        self.provides_horizontal_content = True
        self.provides_vertical_content = True

        logger.info("RecoveryMode app initialized")

    def generate(self, tilt_state: TiltState, encoder_input: EncoderInput) -> Image:
        """
        Generate the recovery mode frame with recovery instructions.

        :param tilt_state: Current tilt state (unused in recovery mode).
        :param encoder_input: Encoder input (unused in recovery mode).
        :return: Recovery mode frame.
        """
        return CustomFrames.recovery_mode()

    def generate_on_error(self) -> Image:
        """
        Fallback if recovery mode frame rendering itself fails.

        :return: Black frame.
        """
        logger.critical("RecoveryMode app itself encountered an error!")
        return CustomFrames.black()
