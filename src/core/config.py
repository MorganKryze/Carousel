"""Configuration management with generational versioning and automatic fallback."""

import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from core.config_helpers import (
    ensure_metadata_defaults,
    extract_generation_id,
    get_all_generation_filenames,
    get_sorted_working_generation_paths,
    get_version_from_pyproject,
    load_yaml_file,
    save_yaml_file,
    validate_config_structure,
)
from utils.path import PathTo


class Configuration:
    """Singleton configuration manager with generational versioning.

    Handles loading, saving, and accessing configuration data with automatic
    fallback to previous working versions and garbage collection of old files.
    """

    _instance: Optional["Configuration"] = None

    def __new__(cls) -> "Configuration":
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(Configuration, cls).__new__(cls)
            cls._instance._initialize()
            cls._instance._load()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize configuration state on creation."""
        self.file_path: str = ""
        self.latest_generation_id: int = 0
        self.latest_working_generation_id: int = 0
        self.configuration_dictionary: Dict[str, Any] = {}

        self.keep_working_generations: int = 10
        self.keep_broken_generations: int = 5
        self.max_generation_age_days: int = 30

    def _load(self) -> None:
        """Load configuration from disk.

        Checks for safe mode first. If safe mode trigger exists, loads
        safemode.config.yaml. Otherwise, attempts to load the latest working
        generation. Falls back through older generations if the latest one is
        invalid. Cleans up old files after loading.
        """
        logger.info("Loading configuration...")

        # Check if we should enter/continue safe mode
        if self._should_enter_safe_mode():
            logger.warning("Safe mode detected - loading safemode.config.yaml")
            self._load_safe_mode_config()
            return

        self.latest_generation_id = self.get_latest_generation_id()
        self.latest_working_generation_id = self.get_latest_working_generation_id()

        if self.latest_generation_id == 0:
            self.create_new_configuration_from_template()

        loaded = self._load_latest_working_config()
        if not loaded:
            logger.warning("No valid configuration found. Rebuilding from template.")
            self.create_new_configuration_from_template()
            loaded = self._load_latest_working_config()
            if not loaded:
                self.critical_exit("Failed to load any valid configuration.")

        self._cleanup_generations()

    def create_new_configuration_from_template(self) -> None:
        """Create a new generation from the template configuration file.

        Raises:
            Calls critical_exit if template not found or parsing fails.
        """
        logger.info("Using template config file to create a new config.")
        template_file_path = PathTo.TEMPLATE_CONFIG_FILE

        template_data = load_yaml_file(template_file_path)
        if template_data is None:
            self.critical_exit(
                f"Failed to load template config file: {template_file_path}"
            )

        template_data["Metadata"]["id"] = 1
        template_data["Metadata"]["version"] = get_version_from_pyproject()
        template_data["Metadata"]["created_at"] = datetime.now().isoformat(
            sep=" ", timespec="minutes"
        )
        logger.debug("Metadata updated with current time and version.")

        if not self.create_new_config_generation(template_data):
            self.critical_exit(
                "Failed to create a new configuration generation from template."
            )

    def create_new_config_generation(self, config: Dict[str, Any]) -> bool:
        """Create and save a new configuration generation.

        Validates metadata, assigns the next generation ID, and atomically
        saves the configuration to disk. Updates internal state only on success.

        :param config: The configuration dictionary to save.
        :return: True if generation created successfully, False otherwise.
        """
        if not os.path.exists(PathTo.GENERATIONS_FOLDER):
            os.makedirs(PathTo.GENERATIONS_FOLDER)
            logger.debug("Generations folder created.")

        working_config = deepcopy(config)
        if not self._ensure_metadata(working_config):
            logger.error("Configuration metadata missing or invalid.")
            return False

        expected_id = self.latest_generation_id + 1
        working_config["Metadata"]["id"] = expected_id
        working_config["Metadata"]["origin"] = working_config["Metadata"].get(
            "origin", "user"
        )
        if expected_id > 1 and working_config["Metadata"]["origin"] != "user":
            working_config["Metadata"]["origin"] = "user"

        if not self.save(working_config):
            logger.error(f"Failed to save new generation with ID {expected_id}")
            return False

        # Update state after successful save
        self.latest_generation_id = expected_id
        self.latest_working_generation_id = expected_id
        self.configuration_dictionary = working_config
        self.file_path = os.path.join(
            PathTo.GENERATIONS_FOLDER, f"generation_{expected_id}.yaml"
        )
        logger.info(f"New generation created: {self.file_path}")
        return True

    def save(self, config: Dict[str, Any], is_broken: bool = False) -> bool:
        """Save configuration to disk atomically.

        Writes to a temporary file, syncs to disk, then atomically replaces
        the target file to prevent corruption.

        :param config: The configuration dictionary to save.
        :param is_broken: If True, saves with .broken.yaml extension.
        :return: True if save succeeded, False otherwise.
        """
        config_id = config.get("Metadata", {}).get("id")
        normal_path = os.path.join(
            PathTo.GENERATIONS_FOLDER, f"generation_{config_id}.yaml"
        )
        broken_path = normal_path.replace(".yaml", ".broken.yaml")
        target_path = broken_path if is_broken else normal_path

        return save_yaml_file(target_path, config)

    def get(self, *keys: str, default: Any = None, required: bool = False) -> Any:
        """Get a configuration value using nested key path.

        :param keys: Variable number of keys to navigate hierarchy.
        :param default: Default value if key path not found.
        :param required: If True, exit if key missing or None.

        :return: Value at key path, or default if not found.
        """
        if not keys:
            return self.configuration_dictionary

        current = self.configuration_dictionary
        key_path = " -> ".join(keys)

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                logger.debug(f"Key path not found: {key_path}")
                if required and default is None:
                    self.critical_exit(f"Required key path not found: {key_path}")
                return default

        if required and current is None:
            self.critical_exit(f"Required key path has None value: {key_path}")

        logger.debug(f"Found value at: {key_path}")
        return current

    def get_from_module(
        self,
        module_name: str,
        *keys: str,
        default: Any = None,
        required: bool = False,
    ) -> Any:
        """Get a value from a module's configuration.

        :param module_name: Name of the module.
        :param keys: Variable number of keys in module config.
        :param default: Default value if not found.
        :param required: If True, exit if key missing or None.

        :return: Value from module config, or default.
        """
        return self.get(
            "Modules", module_name, *keys, default=default, required=required
        )

    def get_from_app(
        self,
        app_name: str,
        *keys: str,
        default: Any = None,
        required: bool = False,
    ) -> Any:
        """Get a value from an app's configuration.

        :param app_name: Name of the app.
        :param keys: Variable number of keys in app config.
        :param default: Default value if not found.
        :param required: If True, exit if key missing or None.
        :return: Value from app config, or default.
        """
        return self.get("Apps", app_name, *keys, default=default, required=required)

    def get_from_app_meta(
        self,
        app_name: str,
        *keys: str,
        default: Any = None,
        required: bool = False,
    ) -> Any:
        """Get a value from an app's metadata.

        :param app_name: Name of the app.
        :param keys: Variable number of keys in app meta.
        :param default: Default value if not found.
        :param required: If True, exit if key missing or None.

        :return: Value from app metadata, or default.
        """
        return self.get(
            "Apps", app_name, "meta", *keys, default=default, required=required
        )

    def get_from_app_config(
        self,
        app_name: str,
        *keys: str,
        default: Any = None,
        required: bool = False,
    ) -> Any:
        """Get a value from an app's config section.

        :param app_name: Name of the app.
        :param keys: Variable number of keys in app config.
        :param default: Default value if not found.
        :param required: If True, exit if key missing or None.

        :return: Value from app config section, or default.
        """
        return self.get(
            "Apps", app_name, "config", *keys, default=default, required=required
        )

    def set(self, *keys: str, value: Any) -> bool:
        """Set a configuration value using nested key path.

        :param keys: Variable number of keys to navigate hierarchy.
        :param value: The value to set.

        :return: True if set succeeded, False otherwise.
        """
        if not keys:
            logger.error("No keys provided to set a value.")
            return False
        try:
            current = self.configuration_dictionary
            for key in keys[:-1]:
                if key not in current or not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]

            current[keys[-1]] = value
            key_path = " -> ".join(keys)
            logger.info(f"Set value at: {key_path} to {value}")
            return True
        except Exception as e:
            key_path = " -> ".join(keys)
            logger.error(f"Failed to set value at {key_path}: {e}")
            return False

    def get_app_names_in_order(self) -> list[str]:
        """Get all app names sorted by their configured order.

        Returns app names sorted by the 'order' field in the configuration.
        Apps with invalid or missing order values are placed at the end.

        :return: List of app names sorted by order.
        """
        apps = self.get("Apps", default={})
        if not isinstance(apps, dict):
            logger.warning("Apps configuration is not a dictionary.")
            return []

        app_list = []
        for app_name, app_config in apps.items():
            if isinstance(app_config, dict):
                order = app_config.get("order", float("inf"))
                if not isinstance(order, int):
                    logger.warning(
                        f"App '{app_name}' has invalid order value: {order}. "
                        "Placing at the end."
                    )
                    order = float("inf")
                app_list.append((app_name, order))

        app_list.sort(key=lambda x: x[1])
        return [app_name for app_name, _ in app_list]

    def get_generation_filenames(self) -> list[str]:
        """Get all YAML generation filenames from the generations folder.

        :return: List of filenames (both working and broken).
        """
        return get_all_generation_filenames(PathTo.GENERATIONS_FOLDER)

    def get_latest_generation_id(self) -> int:
        """Get the latest generation ID (working or broken).

        :return: Latest generation ID, or 0 if no generations exist.
        """
        filenames = self.get_generation_filenames()
        if not filenames:
            return 0

        latest_id = 0
        for filename in filenames:
            try:
                generation_id = extract_generation_id(filename)
                if generation_id > latest_id:
                    latest_id = generation_id
            except (ValueError, IndexError):
                logger.error(f"Invalid generation file name: {filename}")

        logger.debug(f"Latest generation ID found: {latest_id}")
        return latest_id

    def get_latest_working_generation_id(self) -> int:
        """Get the latest working (non-broken) generation ID.

        :return: Latest working generation ID, or 0 if none exist.
        """
        filenames = self.get_generation_filenames()
        if not filenames:
            return 0

        latest_id = 0
        for filename in filenames:
            try:
                if filename.endswith(".broken.yaml"):
                    continue
                generation_id = extract_generation_id(filename)
                if generation_id > latest_id:
                    latest_id = generation_id
            except (ValueError, IndexError):
                logger.error(f"Invalid generation file name: {filename}")

        logger.debug(f"Latest working generation ID found: {latest_id}")
        return latest_id

    def get_latest_working_generation_filepath(self) -> str:
        """Get the filepath of the latest working generation.

        :return: Full path to latest working generation, or empty string if none exist.
        """
        latest_id = self.get_latest_working_generation_id()
        if latest_id == 0:
            return ""

        return os.path.join(PathTo.GENERATIONS_FOLDER, f"generation_{latest_id}.yaml")

    def flag_current_generation_as_broken(self, reason: str) -> None:
        """Mark the current generation as broken and save the reason.

        :param reason: Description of why the generation is broken.
        """
        try:
            if not self.file_path:
                logger.error("No configuration file path set to flag as broken.")
                return

            self.set("Metadata", "is_broken", value=True)
            self.set("Metadata", "broken_reason", value=reason)

            original_path = self.file_path
            broken_path = original_path.replace(".yaml", ".broken.yaml")

            if not self.save(self.configuration_dictionary, is_broken=True):
                logger.error(f"Failed to save broken configuration to {broken_path}")
                return

            if os.path.exists(original_path):
                os.remove(original_path)

            logger.info(f"Generation {self.latest_generation_id} marked as broken.")

        except Exception as e:
            logger.error(f"Failed to flag generation as broken: {e}")

    def critical_exit(self, reason: str) -> None:
        """Enter safe mode due to critical error.

        Guards against re-entry if already in safe mode (would cause infinite loop).
        Otherwise:
        1. Flags current generation as broken with reason
        2. Writes safe mode trigger file (JSON) with reason and generation ID
        3. Restarts system to load safemode.config.yaml

        :param reason: Description of the critical error.
        """
        logger.critical(f"Critical error occurred: {reason}")

        if self.is_safe_mode():
            logger.critical(
                "Critical error occurred inside safe mode itself — cannot re-enter. "
                "Manual intervention required. Exiting."
            )
            logger.complete()
            sys.exit(1)

        logger.warning("Entering safe mode...")

        self.flag_current_generation_as_broken(reason)

        self.restart()

    def restart(self) -> None:
        """Restart the program by replacing the current process.

        IMPORTANT: Hardware resources (GPIO pins, SPI/I2C buses, display) must be
        explicitly released before restart, especially on Raspberry Pi. Without cleanup,
        the restarted process cannot claim these kernel-level resources.

        Note: This will trigger multiprocessing resource_tracker warnings about leaked
        semaphores. These warnings are cosmetic and can be safely ignored - the OS
        cleans up semaphores when the process exits, but hardware resources (GPIO)
        require explicit cleanup to prevent access failures on restart.
        """
        try:
            from core.game_loop import GameLoop

            logger.warning(
                "Restarting application. Releasing hardware resources first."
            )

            if GameLoop.is_initialized():
                logger.info("Releasing GPIO, display, and input hardware...")
                try:
                    GameLoop().cleanup()
                    logger.info("Hardware cleanup completed successfully.")
                except Exception as cleanup_error:
                    logger.error(
                        f"Error during hardware cleanup: {cleanup_error}", exc_info=True
                    )
                    logger.warning("Proceeding with restart despite cleanup errors.")

            logger.warning(
                "NOTE: A multiprocessing resource_tracker warning may appear below. "
                "This is EXPECTED and can be safely IGNORED. It's a cosmetic warning "
                "from the RGB matrix library - the OS cleans up these resources automatically."
            )
            logger.info(f"Executing: {sys.executable} with args: {sys.argv}")
            logger.complete()

            os.execv(sys.executable, [sys.executable, *sys.argv])
        except Exception as e:
            logger.critical(f"Failed to restart process: {e}", exc_info=True)
            logger.complete()
            sys.exit(1)

    def _should_enter_safe_mode(self) -> bool:
        """Check if system should enter safe mode.

        Safe mode is triggered when the latest generation file is broken,
        i.e. the latest overall generation ID exceeds the latest working one.
        No separate trigger file is needed — the presence of a .broken.yaml
        as the newest generation IS the signal.

        :return: True if latest generation is broken, False otherwise.
        """
        latest_id = self.get_latest_generation_id()
        if latest_id == 0:
            return False
        working_id = self.get_latest_working_generation_id()
        return working_id < latest_id

    def get_safe_mode_info(self) -> Optional[Dict[str, Any]]:
        """Return safe mode info derived from the broken generation's YAML metadata.

        Reads the broken generation file directly — no separate trigger file needed.

        :return: Dict with 'reason', 'broken_generation_id', 'timestamp', or None.
        """
        latest_id = self.get_latest_generation_id()
        if latest_id == 0:
            return None
        working_id = self.get_latest_working_generation_id()
        if working_id >= latest_id:
            return None

        broken_path = os.path.join(
            PathTo.GENERATIONS_FOLDER, f"generation_{latest_id}.broken.yaml"
        )
        if not os.path.exists(broken_path):
            return {
                "reason": f"Generation {latest_id} is broken (file not found)",
                "broken_generation_id": latest_id,
                "timestamp": "",
            }

        data = self._load_yaml(broken_path)
        if data is None:
            return {
                "reason": f"Generation {latest_id} is broken (unreadable)",
                "broken_generation_id": latest_id,
                "timestamp": "",
            }

        metadata = data.get("Metadata", {})
        return {
            "reason": metadata.get("broken_reason") or "Unknown critical error",
            "broken_generation_id": latest_id,
            "timestamp": str(metadata.get("created_at", "")),
        }

    def get_broken_generation_for_editing(self) -> Optional[Dict[str, Any]]:
        """Load the broken generation data so the webserver can offer editing.

        Uses the broken_generation_id from the trigger file to locate the
        .broken.yaml file and load its contents.

        :return: Broken config dict if found and parseable, None otherwise.
        """
        info = self.get_safe_mode_info()
        if info is None:
            return None

        broken_id = info.get("broken_generation_id", 0)
        if broken_id <= 0:
            return None

        broken_path = os.path.join(
            PathTo.GENERATIONS_FOLDER, f"generation_{broken_id}.broken.yaml"
        )
        if not os.path.exists(broken_path):
            logger.warning(f"Broken generation file not found: {broken_path}")
            return None

        config_data = self._load_yaml(broken_path)
        if config_data is None:
            logger.error(f"Failed to parse broken generation: {broken_path}")
        return config_data

    def apply_recovery_config(self, config: Dict[str, Any]) -> bool:
        """Save a corrected config as a new generation, without clearing safe mode.

        Validates the config first. Caller is responsible for clearing safe mode
        and restarting afterwards.

        :param config: The corrected configuration dictionary to save.
        :return: True if the new generation was created successfully.
        """
        is_valid, error_reason = self._validate_config(config)
        if not is_valid:
            logger.error(
                f"Recovery config is invalid, refusing to save: {error_reason}"
            )
            return False

        # Strip the broken flag if it was carried over from the broken generation
        config = deepcopy(config)
        config.setdefault("Metadata", {})["is_broken"] = False
        config["Metadata"]["broken_reason"] = None

        return self.create_new_config_generation(config)

    def clear_safe_mode(self) -> bool:
        """Delete the broken generation file to allow normal operation on next restart.

        The broken .yaml file IS the safe mode trigger. Removing it causes
        _should_enter_safe_mode() to return False on the next boot.
        Called after the user has chosen a recovery action; caller must restart.

        :return: True if cleared (or already clear), False on error.
        """
        latest_id = self.get_latest_generation_id()
        if latest_id == 0:
            logger.warning("No generation files found when clearing safe mode")
            return True

        working_id = self.get_latest_working_generation_id()
        if working_id >= latest_id:
            logger.debug("Safe mode already clear — latest generation is working")
            return True

        broken_path = os.path.join(
            PathTo.GENERATIONS_FOLDER, f"generation_{latest_id}.broken.yaml"
        )
        if not os.path.exists(broken_path):
            logger.warning(
                f"Broken generation file not found when clearing: {broken_path}"
            )
            return False

        try:
            os.remove(broken_path)
            logger.info(f"Safe mode cleared: removed {broken_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear safe mode: {e}")
            return False

    def _load_safe_mode_config(self) -> None:
        """Load the safemode.config.yaml file.

        This is a minimal configuration with no apps enabled,
        used when system enters safe mode after a critical error.
        """
        safe_mode_path = PathTo.SAFEMODE_CONFIG_FILE

        if not os.path.exists(safe_mode_path):
            logger.critical(f"Safe mode config not found: {safe_mode_path}")
            logger.critical("Cannot enter safe mode without safemode.config.yaml!")
            sys.exit(1)

        config_data = self._load_yaml(safe_mode_path)
        if config_data is None:
            logger.critical("Failed to parse safemode.config.yaml!")
            sys.exit(1)

        is_valid, error_reason = self._validate_config(config_data)
        if not is_valid:
            logger.critical(f"Safe mode config is invalid: {error_reason}")
            sys.exit(1)

        self.configuration_dictionary = config_data
        self.file_path = safe_mode_path
        logger.info(f"Safe mode configuration loaded: {safe_mode_path}")

    def is_safe_mode(self) -> bool:
        """Check if currently running in safe mode.

        :return: True if in safe mode, False otherwise.
        """
        return os.path.abspath(self.file_path) == os.path.abspath(
            PathTo.SAFEMODE_CONFIG_FILE
        )

    def _ensure_metadata(self, config: Dict[str, Any]) -> bool:
        """Ensure config has valid metadata section with required fields.

        :param config: Configuration dictionary to validate and fix.
        :return: True if metadata is now valid, False if not a dict.
        """
        return ensure_metadata_defaults(config)

    def _validate_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate that config has required structure.

        :param config: Configuration dictionary to validate.

        :return: Tuple of (is_valid, error_reason).
        """
        return validate_config_structure(config)

    def _load_yaml(self, path: str) -> Optional[Dict[str, Any]]:
        """Load and parse a YAML configuration file.

        :param path: File path to load.

        :return: Parsed config dict, or None if parsing failed.
        """
        return load_yaml_file(path)

    def _load_latest_working_config(self) -> bool:
        """Load the latest valid configuration from disk.

        Tries working generations in descending order until one passes
        validation. Marks invalid ones as broken.

        :return: True if a valid config was loaded, False otherwise.
        """
        candidates = self._get_sorted_working_paths()

        for path in candidates:
            config_data = self._load_yaml(path)
            if config_data is None:
                self._mark_generation_broken(path, "Failed to parse YAML")
                continue

            is_valid, error_reason = self._validate_config(config_data)
            if not is_valid:
                self._mark_generation_broken(path, error_reason, config_data)
                continue

            self.configuration_dictionary = config_data
            self.file_path = path
            self.latest_generation_id = self.get_latest_generation_id()
            self.latest_working_generation_id = self._extract_id_from_path(path)
            logger.info(f"Successfully loaded configuration: {path}")
            return True

        logger.error("No valid working configuration found.")
        return False

    def _mark_generation_broken(
        self,
        path: str,
        reason: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a generation file as broken and save it with reason.

        :param path: Path to the generation file.
        :param reason: Reason why it's being marked broken.
        :param config: Config dict (for detailed broken file), or None for simple rename.
        """
        broken_path = path.replace(".yaml", ".broken.yaml")

        try:
            if config is not None:
                config = deepcopy(config)
                self._ensure_metadata(config)
                config["Metadata"]["is_broken"] = True
                config["Metadata"]["broken_reason"] = reason
                self.save(config, is_broken=True)
                if os.path.exists(path):
                    os.remove(path)
            else:
                if os.path.exists(path):
                    os.replace(path, broken_path)

            logger.warning(f"Marked configuration as broken: {broken_path}")

        except OSError as e:
            logger.error(f"Failed to mark configuration as broken: {e}")

    def _get_sorted_working_paths(self) -> list[str]:
        """Get working generation paths sorted in descending order by ID.

        :return: List of paths to working (non-broken) generations, newest first.
        """
        return get_sorted_working_generation_paths(PathTo.GENERATIONS_FOLDER)

    def _extract_id_from_path(self, path: str) -> int:
        """Extract generation ID from a file path.

        :param path: Path to generation file.

        :return: Generation ID, or 0 if path format is invalid.
        """
        filename = os.path.basename(path)
        return extract_generation_id(filename)

    def _cleanup_generations(self) -> None:
        """Apply retention policy and delete old generation files.

        Keeps the specified number of working and broken generations,
        plus any within the age limit. Cleans up the rest.
        """
        try:
            filenames = self.get_generation_filenames()
            if not filenames:
                return

            now = datetime.now()
            working: list[Tuple[int, str]] = []
            broken: list[Tuple[int, str]] = []

            for filename in filenames:
                if not filename.startswith("generation_"):
                    continue

                path = os.path.join(PathTo.GENERATIONS_FOLDER, filename)
                generation_id = self._extract_id_from_path(path)

                if generation_id <= 0:
                    continue

                if filename.endswith(".broken.yaml"):
                    broken.append((generation_id, path))
                else:
                    working.append((generation_id, path))

            working.sort(key=lambda item: item[0], reverse=True)
            broken.sort(key=lambda item: item[0], reverse=True)

            keep_working = {
                path for _, path in working[: self.keep_working_generations]
            }
            keep_broken = {path for _, path in broken[: self.keep_broken_generations]}

            max_age = timedelta(days=self.max_generation_age_days)
            for _, path in working + broken:
                if path in keep_working or path in keep_broken:
                    continue

                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if now - mtime <= max_age:
                        continue
                except OSError:
                    pass

                try:
                    os.remove(path)
                    logger.debug(f"Deleted old configuration generation: {path}")
                except OSError as e:
                    logger.warning(f"Failed to delete old generation {path}: {e}")

        except Exception as e:
            logger.warning(f"Generation cleanup failed: {e}")
