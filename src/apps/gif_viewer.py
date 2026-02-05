import os
from typing import Callable, Dict, List

from loguru import logger
from PIL import Image, ImageDraw, ImageSequence

from io.display_controller import DisplayController
from core.config import Configuration
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState
from models.application import Application
from core.path import PathTo

WHITE = (230, 255, 255)


class GifPlayer(Application):
    def __init__(self, callbacks: Dict[str, Callable]):
        """
        Initialize the GifPlayer with callbacks.

        :param callbacks: Dict[str, Callable]: Dictionary of callback functions.
        """
        super().__init__(callbacks)
        if self.status == ServiceStatus.DISABLED:
            logger.info(
                f"[{self.__class__.__name__}] Stopped initialization due to disabled status."
            )
            return

        self.play_limit = Configuration.get_from_app_config(
            self.__class__.__name__, "play_limit", required=True
        )
        if self.play_limit < 1:
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                "Play limit must be greater than or equal to 1."
            )
        self.led_cols = DisplayController().led_cols
        self.led_rows = DisplayController().led_rows
        self.animations = self.load_animations()
        if not self.animations:
            self.status = ServiceStatus.ERROR_APP_CONFIG
            logger.error(
                f"[{self.__class__.__name__}] No GIFs found, nothing to show up."
            )
        self.current_animation_index = 0
        self.selection_mode = False
        self.current_frame_index = 0
        self.was_horizontal = True
        self.auto_play_mode = False
        self.play_count = 0

        if self.status == ServiceStatus.ERROR_APP_CONFIG:
            logger.error(
                f"[{self.__class__.__name__}] Application configuration errors, please check the configuration before restarting."
            )
            return

        self.status = ServiceStatus.RUNNING
        logger.info(f"[{self.__class__.__name__}] Running.")

    def generate(
        self, tilt_state: TiltState, encoder_input: EncoderInput
    ) -> Image:
        """
        Generate the frame to draw on the LED matrix.

        :param tilt_state: TiltState: The current tilt state of the device.
        :param encoder_input: EncoderInput: The status of the encoder input.
        :return: Image: The generated frame.
        """
        super().generate(tilt_state, encoder_input)
        try:
            if encoder_input == EncoderInput.LONG_PRESS:
                logger.debug("Toggling selection mode.")
                self.selection_mode = not self.selection_mode

            if encoder_input == EncoderInput.DOUBLE_PRESS:
                logger.debug("Toggling auto play mode.")
                self.auto_play_mode = not self.auto_play_mode
                if self.auto_play_mode:
                    self.play_count = 0
                    self.current_animation_index = (
                        self.current_animation_index + 1
                    ) % len(self.animations)

            if self.selection_mode:
                if encoder_input == EncoderInput.INCREASE_CLOCKWISE:
                    logger.debug("Switching to next GIF.")
                    self.current_animation_index = (
                        self.current_animation_index + 1
                    ) % len(self.animations)
                    self.current_frame_index = 0
                elif encoder_input == EncoderInput.DECREASE_COUNTERCLOCKWISE:
                    logger.debug("Switching to previous GIF.")
                    self.current_animation_index = (
                        self.current_animation_index - 1
                    ) % len(self.animations)
                    self.current_frame_index = 0
            else:
                if encoder_input == EncoderInput.SINGLE_PRESS:
                    self.callbacks["toggle_display"]()
                elif encoder_input == EncoderInput.INCREASE_CLOCKWISE:
                    self.callbacks["switch_next_app"]()
                elif encoder_input == EncoderInput.DECREASE_COUNTERCLOCKWISE:
                    self.callbacks["switch_prev_app"]()

            current_gif = ImageSequence.Iterator(
                self.animations[self.current_animation_index % len(self.animations)]
            )
            try:
                frame = current_gif[self.current_frame_index].convert("RGB")
            except IndexError:
                logger.debug(
                    "Reached the end of the GIF. Restarting from the beginning."
                )
                self.current_frame_index = 0
                frame = current_gif[self.current_frame_index].convert("RGB")

            self.current_frame_index += 1

            if self.auto_play_mode:
                frame_count = sum(
                    1
                    for _ in ImageSequence.Iterator(
                        self.animations[
                            self.current_animation_index % len(self.animations)
                        ]
                    )
                )
                if self.current_frame_index >= frame_count:
                    self.play_count += 1
                    if self.play_count >= self.play_limit:
                        self.play_count = 0
                        self.current_animation_index = (
                            self.current_animation_index + 1
                        ) % len(self.animations)
                    self.current_frame_index = 0

            draw = ImageDraw.Draw(frame)
            if self.selection_mode:
                draw.rectangle(
                    (0, 0, self.led_cols - 1, self.led_rows - 1), outline=WHITE
                )

            return frame
        except Exception as e:
            self.status = ServiceStatus.ERROR_APP_INTERNAL
            logger.error(f"Error generating frame: {e}")
            return self.generate_on_error()

    def load_animations(self) -> List[Image.Image]:
        """
        Loads all GIFs from their respective folder.

        :return: List[Image.Image]: List of loaded GIF images.
        """
        logger.debug("Loading GIFs.")
        try:
            result = []
            for filename in os.listdir(PathTo.GIF_FOLDER):
                if filename.endswith(".gif"):
                    logger.debug(f"Loading GIF: {filename}")
                    result.append(Image.open(os.path.join(PathTo.GIF_FOLDER, filename)))

            logger.info(f"All {len(result)} GIFs loaded successfully.")
            return result
        except Exception as e:
            logger.error(f"Error loading GIFs: {e}")
            return []
