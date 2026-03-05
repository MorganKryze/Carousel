"""App model class."""

from typing import Callable, Dict

from loguru import logger
from PIL import Image

from core.app_catalog import APP_CATALOG
from core.system_context import SystemContext
from display.custom_frames import CustomFrames
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState


class Application:
    """
    Base application class with singleton SystemContext dependency injection.
    """

    def __init__(self, context: SystemContext, callbacks: Dict[str, Callable]):
        """
        Initialize application with injected singleton context.

        :param context: Singleton SystemContext instance.
        :param callbacks: Dictionary of callback functions for app interactions.
        """
        if not SystemContext.is_initialized():
            logger.error(f"[{self.__class__.__name__}] SystemContext not initialized!")
            raise RuntimeError("SystemContext must be initialized before creating apps")

        self.context = context
        self.callbacks = callbacks
        self.status: ServiceStatus = ServiceStatus.INITIALIZING

        app_key = self.__class__.__name__
        config = context.config

        logger.debug(f"[{app_key}] Initializing metadata from catalog...")
        self.enabled = config.get_from_app(app_key, "enabled", required=True)

        catalog_entry = APP_CATALOG.get(app_key)
        if catalog_entry is None:
            logger.error(f"[{app_key}] Not found in APP_CATALOG!")
            raise RuntimeError(f"App '{app_key}' is not registered in APP_CATALOG")

        self.name: str = catalog_entry.name
        self.description: str = catalog_entry.description
        self.provides_horizontal_content = "horizontal" in catalog_entry.orientations
        self.provides_vertical_content = "vertical" in catalog_entry.orientations

        logger.debug(f"[{app_key}] Initializing configuration...")

        if not self.enabled:
            self.status = ServiceStatus.DISABLED

    def generate(self, tilt_state: TiltState, encoder_input: EncoderInput) -> Image:
        """
        Generate the frame for the app.
        This method should be extended by subclasses to implement specific frame generation logic.

        :param tilt_state: TiltState: The current tilt state of the device.
        :param encoder_input: EncoderInput: The status of the encoder input.
        :return: Image: The generated frame.
        """
        if self.status != ServiceStatus.RUNNING:
            return self.generate_on_error()

        if tilt_state is TiltState.HORIZONTAL and not self.provides_horizontal_content:
            return CustomFrames.turn_frame(self.name, "horizontal")

        if tilt_state is TiltState.VERTICAL and not self.provides_vertical_content:
            return CustomFrames.turn_frame(self.name, "vertical")

    def generate_on_error(self) -> Image:
        """
        Generate the frame for the app when an error occurs.

        :return: Image: The error frame.
        """
        return CustomFrames.error(self.status)
