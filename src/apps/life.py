import os
import random
from datetime import datetime, timedelta
from typing import Callable, Dict

import numpy as np
from loguru import logger
from PIL import Image, ImageDraw
from scipy.signal import convolve2d

from core.system_context import SystemContext
from enums.encoder_input import EncoderInput
from enums.service_status import ServiceStatus
from enums.tilt_input import TiltState
from hardware.display_controller import DisplayController
from models.application import Application
from utils.path import PathTo


class GameOfLife(Application):
    def __init__(self, context: SystemContext, callbacks: Dict[str, Callable]):
        super().__init__(context, callbacks)
        if self.status == ServiceStatus.DISABLED:
            logger.info("Stopped initialization due to disabled status.")
            return

        self.color = (255, 255, 255)
        self.initial_states = [
            lambda: generate_random_state(self.context.display),
            lambda: fetch_pattern(
                os.path.join(PathTo.DEFAULT_LIFE_PATTERNS_FOLDER, "centinal"),
            ),
            lambda: fetch_pattern(
                os.path.join(PathTo.DEFAULT_LIFE_PATTERNS_FOLDER, "achim_p144"),
            ),
            lambda: fetch_pattern(
                os.path.join(PathTo.DEFAULT_LIFE_PATTERNS_FOLDER, "pboj_p22"),
            ),
        ]
        self.current_state_index = 0
        self.state = self.initial_states[self.current_state_index]()

        self.status = ServiceStatus.RUNNING
        logger.info("App running.")

    def generate(self, tilt_state: TiltState, encoder_input: EncoderInput) -> Image:
        """
        Generate the frame for the GameOfLifeScreen app.

        :param tilt_state: TiltState: The current tilt state of the device.
        :param encoder_input: EncoderInput: The status of the encoder input.
        :return: Image: The generated frame.
        """
        super().generate(tilt_state, encoder_input)

        try:
            if encoder_input in [
                EncoderInput.SINGLE_PRESS,
                EncoderInput.LONG_PRESS,
            ]:
                if encoder_input == EncoderInput.LONG_PRESS:
                    self.current_state_index = (self.current_state_index + 1) % len(
                        self.initial_states
                    )
                self.state = self.initial_states[self.current_state_index]()
                self.color = generate_new_color()
            elif encoder_input == EncoderInput.INCREASE_CLOCKWISE:
                self.callbacks["switch_next_app"]()
            elif encoder_input == EncoderInput.DECREASE_COUNTERCLOCKWISE:
                self.callbacks["switch_prev_app"]()

            end_time = datetime.now() + timedelta(seconds=0.1)

            old_state = self.state
            frame = Image.new(
                "RGB",
                (self.context.display.led_cols, self.context.display.led_rows),
                (0, 0, 0),
            )
            draw = ImageDraw.Draw(frame)

            new_state = life_step(old_state)
            for i in range(self.context.display.led_rows):
                for j in range(self.context.display.led_cols):
                    if new_state[i][j] == 1:
                        draw.point((j, i), fill=self.color)

            self.state = new_state

            while datetime.now() < end_time:
                pass

            return frame
        except Exception as e:
            self.status = ServiceStatus.ERROR_APP_INTERNAL
            logger.error(f"Error generating frame: {e}")
            return self.generate_on_error()


def life_step(state: np.ndarray) -> np.ndarray:
    """
    Perform a step in the Game of Life using scipy tools.

    Args:
        state (np.ndarray): The current state of the Game of Life.

    Returns:
        np.ndarray: The new state of the Game of Life.
    """
    neighbors_count = (
        convolve2d(state, np.ones((3, 3)), mode="same", boundary="wrap") - state
    )
    return (neighbors_count == 3) | (state & (neighbors_count == 2))


def get_num_neighbors(
    state: np.ndarray, i: int, j: int, display: DisplayController
) -> int:
    """
    Get the number of live neighbors for a cell in the Game of Life.

    Args:
        state (np.ndarray): The current state of the Game of Life.
        i (int): The row index of the cell.
        j (int): The column index of the cell.

    Returns:
        int: The number of live neighbors.
    """
    num_on = 0

    for di in [-1, 0, 1]:
        for dj in [-1, 0, 1]:
            if di == 0 and dj == 0:
                continue
            if state[(i + di) % display.led_rows][(j + dj) % display.led_cols] == 1:
                num_on += 1

    return num_on


def generate_random_state(display: DisplayController) -> np.ndarray:
    """
    Generate a random initial state for the Game of Life.

    Returns:
        np.ndarray: The random initial state.
    """
    initial_state = np.zeros((display.led_rows, display.led_cols), dtype=int)
    for i in range(display.led_rows):
        for j in range(display.led_cols):
            initial_state[i][j] = random.randint(0, 1)
    return initial_state


def generate_new_color() -> tuple:
    """
    Generate a new random color.

    Returns:
        tuple: A tuple representing the RGB color.
    """
    return (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))


def fetch_pattern(file_location: str) -> np.ndarray:
    """
    Fetch a pattern from a file.

    Args:
        file_location (str): The location of the pattern file.

    Returns:
        np.ndarray: The loaded pattern.
    """
    if not os.path.exists(file_location + ".npy"):
        convert_image(file_location)
    return np.load(file_location + ".npy")


def convert_image(location: str):
    """
    Convert an image to a numpy array and save it.

    Args:
        location (str): The location of the image file.
    """
    image = Image.open(location + ".png")
    width, height = image.size
    image_array = np.array(image.convert("RGB"), dtype=int)
    np.save(
        location + ".npy", (image_array[0:height, 0:width, 0] // 255).astype("int32")
    )
