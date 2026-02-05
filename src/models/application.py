"""App model class."""

from typing import Callable, Dict

from loguru import logger
from PIL import Image

from core.config import Configuration
from display.custom_frames import CustomFrames
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState


class Application:
    """Modules are components that provide resources or functionnalities that can be used by multiple applications."""

    def __init__(self, callbacks: Dict[str, Callable]):
        self.status: ServiceStatus = ServiceStatus.INITIALIZING
        logger.debug(f"[{self.__class__.__name__}] Initializing metadata...")
        self.enabled = Configuration.get_from_app(
            self.__class__.__name__, "enabled", required=True
        )
        self.name: str = Configuration.get_from_app_meta(
            self.__class__.__name__, "name", required=True
        )
        self.description: str = Configuration.get_from_app_meta(
            self.__class__.__name__, "description", required=True
        )
        self.provides_horizontal_content = Configuration.get_from_app_meta(
            self.__class__.__name__, "provides_horizontal_content", required=True
        )
        self.provides_vertical_content = Configuration.get_from_app_meta(
            self.__class__.__name__, "provides_vertical_content", required=True
        )

        logger.debug(f"[{self.__class__.__name__}] Initializing configuration...")
        self.callbacks = callbacks
        self.horizontal_replacement_app_name = Configuration.get_from_app_config(
            self.__class__.__name__, "horizontal_replacement_app"
        )
        self.vertical_replacement_app_name = Configuration.get_from_app_config(
            self.__class__.__name__, "vertical_replacement_app"
        )

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
            replacement_app: Application = self.callbacks["get_app_by_name"](
                self.horizontal_replacement_app_name
            )
            if replacement_app:
                return replacement_app.generate(tilt_state, encoder_input)
            else:
                return CustomFrames.black()

        if tilt_state is TiltState.VERTICAL and not self.provides_vertical_content:
            replacement_app: Application = self.callbacks["get_app_by_name"](
                self.vertical_replacement_app_name
            )
            if replacement_app:
                return replacement_app.generate(tilt_state, encoder_input)
            else:
                return CustomFrames.black()

    def generate_on_error(self) -> Image:
        """
        Generate the frame for the app when an error occurs.

        :return: Image: The error frame.
        """
        return CustomFrames.error(self.status)
