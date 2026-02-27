import argparse
import asyncio

from loguru import logger

from core.config import Configuration
from core.game_loop import GameLoop
from core.network_manager import NetworkManager
from display.animations import Animations
from utils.logs import start_logger
from utils.path import PathTo


async def async_main(use_emulator: bool = False) -> None:
    """
    Main async entry point.
    Orchestrates initialization, loading animation, and game loop execution.
    """

    if not use_emulator:
        logger.info("Network manager enabled (hardware mode)")
        network_manager = NetworkManager()
        if Configuration().is_recovery_mode():
            logger.warning("Recovery mode detected: forcing local hotspot for recovery")
            network_ready = network_manager.init_connectivity(force_hotspot=True)
        else:
            network_ready = network_manager.init_connectivity(force_hotspot=False)

        if network_ready:
            logger.info("Network state: connectivity setup completed")
        else:
            logger.warning(
                "Network state: connectivity setup failed or unavailable; "
                "continuing startup"
            )
    else:
        logger.warning("Network manager disabled (emulator mode)")

    game_loop = GameLoop(use_emulator)

    animations = Animations()

    if use_emulator:
        logger.warning(
            "About to start display rendering. You will see 'RuntimeError: "
            "This event loop is already running' - "
            "this is expected and can be safely ignored."
        )

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
    PathTo.ensure_data_directories()

    log_level = "DEBUG" if args.debug else "WARNING"
    start_logger(file_level="DEBUG", console_level=log_level)

    try:
        asyncio.run(async_main(use_emulator=args.emulator))
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
