"""Helpers for configuration management: validation, utilities, and file operations."""

import os
import socket
import tomllib
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import yaml
from loguru import logger
from pydantic import ValidationError

from core.config_schema import ConfigRoot
from utils.path import PathTo


def get_version_from_pyproject() -> str:
    """Read project version from pyproject.toml.

    :return: Version string, or 'unknown' if not found.
    """
    with open(PathTo.PYPROJECT_FILE, "rb") as file:
        data = tomllib.load(file)
    version = data.get("project", {}).get("version", "unknown")
    return version


def get_addresses() -> Tuple[str, str]:
    """Get local hostname and IP address.

    :return: Tuple of (hostname, local_ip). Returns ('unknown', 'unknown') on failure.
    """
    socket_connection = None
    try:
        hostname = socket.gethostname()
        local_hostname = f"{hostname}.local"
        dummy_target = "10.255.255.255"

        socket_connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_connection.connect((dummy_target, 1))
        local_ip = socket_connection.getsockname()[0]

        return local_hostname, local_ip

    except Exception as e:
        logger.warning(f"Failed to retrieve hostname or local IP: {e}")
        return "unknown", "unknown"

    finally:
        if socket_connection:
            socket_connection.close()


def ensure_metadata_defaults(config: Dict[str, Any]) -> bool:
    """Ensure config has valid metadata section with required fields.

    :param config: Configuration dictionary to validate and fix.
    :return: True if metadata is now valid, False if not a dict.
    """
    metadata = config.get("Metadata")
    if not isinstance(metadata, dict):
        return False

    defaults = {
        "id": 0,
        "version": get_version_from_pyproject(),
        "created_at": datetime.now().isoformat(sep=" ", timespec="minutes"),
        "origin": "user",
        "is_broken": False,
        "broken_reason": None,
    }

    for key, default_value in defaults.items():
        if key not in metadata or metadata[key] is None:
            metadata[key] = default_value

    return isinstance(metadata.get("id"), int)


def _format_pydantic_errors(error: ValidationError, limit: int = 3) -> str:
    """Format pydantic errors into a short, readable summary."""
    items = []
    for entry in error.errors()[:limit]:
        location = ".".join(str(part) for part in entry.get("loc", []))
        message = entry.get("msg", "Invalid value")
        items.append(f"{location}: {message}")
    if len(error.errors()) > limit:
        items.append("...")
    return "; ".join(items)


def validate_config_structure(config: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that config matches the schema.

    :param config: Configuration dictionary to validate.
    :return: Tuple of (is_valid, error_reason).
    """
    if not isinstance(config, dict):
        return False, "Configuration root must be a dictionary."

    if not ensure_metadata_defaults(config):
        return False, "Metadata section is missing or invalid."

    try:
        ConfigRoot.model_validate(config)
        return True, ""
    except ValidationError as error:
        return False, _format_pydantic_errors(error)


def load_yaml_file(path: str) -> Optional[Dict[str, Any]]:
    """Load and parse a YAML configuration file.

    :param path: File path to load.
    :return: Parsed config dict, or None if parsing failed.
    """
    try:
        with open(path, "r") as file:
            config_data = yaml.safe_load(file)
        if config_data is None:
            return None
        return config_data
    except (OSError, yaml.YAMLError) as e:
        logger.error(f"Failed to parse config file {path}: {e}")
        return None


def save_yaml_file(path: str, config: Dict[str, Any]) -> bool:
    """Save configuration to disk atomically.

    Writes to a temporary file, syncs to disk, then atomically replaces
    the target file to prevent corruption.

    :param path: File path to save to.
    :param config: The configuration dictionary to save.
    :return: True if save succeeded, False otherwise.
    """
    temp_path = f"{path}.tmp"

    try:
        if os.path.exists(path):
            logger.warning(f"Configuration file already exists: {path}. Overwriting.")

        with open(temp_path, "w") as file:
            yaml.safe_dump(config, file, default_flow_style=False)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, path)
        logger.info(f"Configuration saved to {path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return False


def extract_generation_id(path_or_filename: str) -> int:
    """Extract generation ID from a file path or filename.

    Expects format: generation_<id>.yaml or generation_<id>.broken.yaml

    :param path_or_filename: Path or filename to extract ID from.
    :return: Generation ID, or 0 if format is invalid.
    """
    filename = os.path.basename(path_or_filename)
    try:
        return int(filename.split("_")[1].split(".")[0])
    except (ValueError, IndexError):
        return 0


def get_sorted_working_generation_paths(
    generations_folder: str,
) -> list[str]:
    """Get working generation paths sorted in descending order by ID.

    :param generations_folder: Path to the generations folder.
    :return: List of paths to working (non-broken) generations, newest first.
    """
    try:
        filenames = os.listdir(generations_folder)
    except FileNotFoundError:
        logger.error(f"Generations folder not found: {generations_folder}")
        return []

    working_files = [
        filename
        for filename in filenames
        if filename.startswith("generation_")
        and not filename.endswith(".broken.yaml")
        and filename.endswith(".yaml")
    ]

    working_files.sort(key=lambda f: extract_generation_id(f), reverse=True)
    return [os.path.join(generations_folder, filename) for filename in working_files]


def get_all_generation_filenames(generations_folder: str) -> list[str]:
    """Get all YAML generation filenames from the generations folder.

    :param generations_folder: Path to the generations folder.
    :return: List of filenames (both working and broken).
    """
    try:
        return [
            filename
            for filename in os.listdir(generations_folder)
            if filename.endswith(".yaml")
        ]
    except FileNotFoundError:
        logger.error(f"Generations folder not found: {generations_folder}")
        return []
