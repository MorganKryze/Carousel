import argparse
import asyncio

from loguru import logger

from core.config import Configuration
from core.game_loop import GameLoop
from core.logs import start_logger
from core.path import PathTo
from display.animations import Animations


async def async_main(use_emulator: bool = False) -> None:
    """
    Main async entry point.
    Orchestrates initialization, loading animation, and game loop execution.
    """
    game_loop = GameLoop(target_fps=10, use_emulator=use_emulator)

    animations = Animations()
    await animations.loading_animation()

    render_task = asyncio.create_task(game_loop.render_loop())

    game_loop.setup_signal_handlers(render_task)

    try:
        await render_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown requested.")
    finally:
        game_loop.running = False

        if not render_task.done():
            render_task.cancel()
            try:
                await render_task
            except asyncio.CancelledError:
                pass

        game_loop.cleanup()


@logger.catch
def main() -> None:
    """
    Synchronous entry point.
    Handles CLI arguments and starts the async event loop.
    """
    parser = argparse.ArgumentParser(description="Carousel LED matrix controller")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--emulator", action="store_true", help="Run in emulator mode")
    args = parser.parse_args()

    PathTo.set_base_directory()
    PathTo.add_library_to_path()

    log_level = "DEBUG" if args.debug else "WARNING"
    start_logger(file_level="DEBUG", console_level=log_level)

    # TODO: by default config should load the last working config, but in case of a failure, for the fallback it might be interesting to be able to reload a config from a specific id
    config = Configuration()
    config.load()

    try:
        asyncio.run(async_main(use_emulator=args.emulator))
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
