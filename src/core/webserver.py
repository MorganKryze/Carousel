import socket
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from flask import Flask, jsonify, redirect, render_template, request, url_for
from loguru import logger

from core.config import Configuration
from utils.path import PathTo


class WebServer:
    """Web server for configuring Carousel settings.

    In normal operation the webserver exposes the current generational config
    for editing.  When the system is in recovery mode it loads the broken generation
    (if available) into a separate ``_recovery_config`` dict so the user can
    edit it, then save a corrected generation before restarting.
    """

    def __init__(self):
        """Initialize the web server and pre-load recovery config if in recovery mode."""
        self.is_connected = False
        self.lock = threading.Lock()
        self.config_manager = Configuration()
        self.app = Flask(
            __name__,
            template_folder=PathTo.TEMPLATES_FOLDER,
            static_folder=PathTo.STATIC_FOLDER,
        )

        # In recovery mode: hold the broken config for editing.  None = not in recovery mode
        # or broken generation could not be loaded.
        self._recovery_config: Optional[Dict[str, Any]] = (
            self.config_manager.get_broken_generation_for_editing()
            if self.config_manager.is_recovery_mode()
            else None
        )

        self._register_routes()
        self.server_thread = None

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------

    def _register_routes(self) -> None:
        """Register all routes with the Flask app."""
        # Landing / home
        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/home", "homepage", self.homepage)

        # Config editing
        self.app.add_url_rule(
            "/section/<section_name>", "edit_section", self.edit_section
        )
        self.app.add_url_rule(
            "/section/<section_name>/<subsection>", "edit_section", self.edit_section
        )
        self.app.add_url_rule(
            "/update", "update_config", self.update_config, methods=["POST"]
        )

        # System control
        self.app.add_url_rule(
            "/restart", "restart_system", self.restart_system, methods=["POST"]
        )
        self.app.add_url_rule(
            "/close", "close_connection", self.close_connection, methods=["POST"]
        )

        # Recovery mode
        self.app.add_url_rule(
            "/recovery-mode", "recovery_mode_page", self.recovery_mode_page
        )
        self.app.add_url_rule(
            "/recovery-mode/apply",
            "recovery_mode_apply",
            self.recovery_mode_apply,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/recovery-mode/rollback",
            "recovery_mode_rollback",
            self.recovery_mode_rollback,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/recovery-mode/generate_new",
            "recovery_mode_generate_new",
            self.recovery_mode_generate_new,
            methods=["POST"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_editable_config(self) -> Dict[str, Any]:
        """Return the config dict that should be presented for editing.

        In recovery mode this is the broken generation loaded at init time
        (so the user can fix and apply it).  In normal operation it is the
        live configuration dictionary.
        """
        if self.config_manager.is_recovery_mode() and self._recovery_config is not None:
            return self._recovery_config
        return self.config_manager.configuration_dictionary

    def _set_editable_config(self, config: Dict[str, Any]) -> None:
        """Persist an in-memory edit back to the appropriate store."""
        if self.config_manager.is_recovery_mode():
            self._recovery_config = config
        else:
            self.config_manager.configuration_dictionary = config

    def save_config(self, config: Dict[str, Any]) -> None:
        """Create a new generation from *config* (normal mode only)."""
        if not self.config_manager.create_new_config_generation(config):
            logger.error("Failed to save configuration update as new generation.")

    def _delayed_restart(self, delay: float = 1.0) -> None:
        """Restart the application process after a short delay."""

        def _do():
            time.sleep(delay)
            self.config_manager.restart()

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Normal routes
    # ------------------------------------------------------------------

    def index(self):
        """Landing page — redirect to recovery mode page when in recovery mode."""
        if self.config_manager.is_recovery_mode():
            return redirect(url_for("recovery_mode_page"))
        with self.lock:
            self.is_connected = True
        return render_template("index.html")

    def homepage(self):
        """Main configuration categories page — redirect when in recovery mode."""
        if self.config_manager.is_recovery_mode():
            return redirect(url_for("recovery_mode_page"))

        config = self.config_manager.configuration_dictionary
        apps = config.get("Apps", {})
        modules = config.get("Modules", {})
        system = config.get("System", {})

        return render_template("home.html", apps=apps, modules=modules, system=system)

    def edit_section(self, section_name, subsection=None):
        """Edit a specific section/subsection of the configuration.

        In recovery mode the BROKEN generation is shown for editing, clearly
        flagged in the template via ``is_recovery_mode``.
        """
        config = self._get_editable_config()
        is_recovery_mode = self.config_manager.is_recovery_mode()

        if section_name in config:
            if subsection and subsection in config[section_name]:
                return render_template(
                    "section.html",
                    section_name=section_name,
                    subsection=subsection,
                    section_data=config[section_name][subsection],
                    is_recovery_mode=is_recovery_mode,
                )
            return render_template(
                "section.html",
                section_name=section_name,
                section_data=config[section_name],
                is_recovery_mode=is_recovery_mode,
            )

        target = (
            url_for("recovery_mode_page") if is_recovery_mode else url_for("homepage")
        )
        return redirect(target)

    def update_config(self):
        """Update the in-memory configuration from the submitted form.

        In recovery mode the edit is staged in ``_recovery_config``; it is only
        persisted when the user clicks *Apply fixed config*.
        """
        config = self._get_editable_config()
        data = request.form.to_dict()

        section = data.get("section")
        subsection = data.get("subsection")

        if section and section in config:
            target = (
                config[section][subsection]
                if subsection and subsection in config[section]
                else config[section]
            )
            skip_keys = {"section", "subsection"}

            for key, value in data.items():
                if key in skip_keys or key not in target:
                    continue
                if isinstance(target[key], bool):
                    target[key] = value.lower() == "true"
                elif isinstance(target[key], int):
                    try:
                        target[key] = int(value)
                    except ValueError:
                        pass
                elif isinstance(target[key], float):
                    try:
                        target[key] = float(value)
                    except ValueError:
                        pass
                else:
                    target[key] = value

            # Stage the change
            self._set_editable_config(config)

        if self.config_manager.is_recovery_mode():
            return redirect(url_for("recovery_mode_page"))

        self.save_config(config)
        return redirect(url_for("homepage"))

    def restart_system(self):
        """Restart the Raspberry Pi (apply hardware-level changes)."""
        logger.info("System restart requested from web interface")

        def _do():
            time.sleep(1)
            subprocess.call(["sudo", "reboot"])

        threading.Thread(target=_do).start()
        return jsonify({"status": "Restarting to apply configuration changes..."})

    def close_connection(self):
        """Close the web connection and re-enable local matrix control."""
        with self.lock:
            self.is_connected = False
        return jsonify({"status": "Connection closed"})

    def is_user_connected(self) -> bool:
        """Check if anyone is connected to the web interface."""
        with self.lock:
            return self.is_connected

    def start(self, port: int, debug: bool) -> threading.Thread:
        """Start the web server in a background daemon thread.

        Uses Waitress for production runtime and Flask's development server only
        when debug mode is explicitly enabled.
        """

        def run_server():
            host = "0.0.0.0"
            if debug:
                logger.warning("Starting Flask development server (debug mode enabled)")
                self.app.run(host=host, port=port, debug=True, use_reloader=False)
                return

            try:
                from waitress import serve

                logger.info("Starting Waitress production server")
                serve(
                    self.app,
                    host=host,
                    port=port,
                    threads=2,
                    connection_limit=20,
                    channel_timeout=30,
                    cleanup_interval=15,
                )
            except ModuleNotFoundError:
                logger.error(
                    "Waitress is not installed; falling back to Flask development server. "
                    "Install dependencies to use production server mode."
                )
                self.app.run(host=host, port=port, debug=False, use_reloader=False)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"Web server started on port {port}")
        return self.server_thread

    # ------------------------------------------------------------------
    # Recovery mode routes
    # ------------------------------------------------------------------

    def recovery_mode_page(self):
        """Dedicated recovery mode page.

        Provides the user with contextual information about the critical error
        and the available recovery actions.
        """
        if not self.config_manager.is_recovery_mode():
            return redirect(url_for("homepage"))

        info = self.config_manager.get_recovery_mode_info() or {}
        reason = info.get("reason", "Unknown critical error")
        broken_id = info.get("broken_generation_id", 0)
        timestamp = info.get("timestamp", "")

        # Determine which recovery options are available
        has_broken_config = self._recovery_config is not None
        previous_working_id = self.config_manager.get_latest_working_generation_id()
        has_previous = previous_working_id > 0

        with self.lock:
            self.is_connected = True

        return render_template(
            "recovery_mode.html",
            reason=reason,
            broken_id=broken_id,
            timestamp=timestamp,
            has_broken_config=has_broken_config,
            has_previous=has_previous,
            previous_working_id=previous_working_id,
        )

    def recovery_mode_apply(self):
        """Apply the (edited) broken config as a new working generation.

        The user has reviewed/fixed the broken config via the section editor.
        This saves it as a new generation, clears recovery mode, and restarts.
        """
        if not self.config_manager.is_recovery_mode():
            return jsonify({"status": "error", "message": "Not in recovery mode"}), 400

        if self._recovery_config is None:
            return jsonify(
                {
                    "status": "error",
                    "message": "No recovery config available to apply",
                }
            ), 400

        logger.info("Recovery mode: applying fixed config as new generation")

        if not self.config_manager.apply_recovery_config(self._recovery_config):
            return jsonify(
                {
                    "status": "error",
                    "message": "Config validation failed — fix the remaining errors before applying",
                }
            ), 422

        if not self.config_manager.clear_recovery_mode():
            return jsonify(
                {
                    "status": "error",
                    "message": "Config saved but failed to clear recovery mode trigger",
                }
            ), 500

        self._delayed_restart()
        return jsonify(
            {"status": "success", "message": "Fixed config applied. Restarting..."}
        )

    def recovery_mode_rollback(self):
        """Restore the previous working generation and exit recovery mode.

        Simply clears the recovery mode trigger; on the next boot ``_load()``
        will naturally pick up the last valid working generation.
        Available only when a previous working generation exists.
        """
        if not self.config_manager.is_recovery_mode():
            return jsonify({"status": "error", "message": "Not in recovery mode"}), 400

        prev_id = self.config_manager.get_latest_working_generation_id()
        if prev_id <= 0:
            return jsonify(
                {
                    "status": "error",
                    "message": "No previous working generation found",
                }
            ), 404

        logger.info(f"Recovery mode: rolling back to generation {prev_id}")

        if not self.config_manager.clear_recovery_mode():
            return jsonify(
                {
                    "status": "error",
                    "message": "Failed to clear recovery mode trigger",
                }
            ), 500

        self._delayed_restart()
        return jsonify(
            {
                "status": "success",
                "message": f"Restoring generation {prev_id}. Restarting...",
            }
        )

    def recovery_mode_generate_new(self):
        """Generate a fresh config from the template and exit recovery mode.

        Available as a last resort when there is no previous working
        generation to roll back to (i.e., generation ID was 1).
        """
        if not self.config_manager.is_recovery_mode():
            return jsonify({"status": "error", "message": "Not in recovery mode"}), 400

        logger.info("Recovery mode: generating fresh config from template")

        try:
            self.config_manager.create_new_configuration_from_template()
        except SystemExit:
            return jsonify(
                {
                    "status": "error",
                    "message": "Failed to generate config from template",
                }
            ), 500

        if not self.config_manager.clear_recovery_mode():
            return jsonify(
                {
                    "status": "error",
                    "message": "Config generated but failed to clear recovery mode trigger",
                }
            ), 500

        self._delayed_restart()
        return jsonify(
            {"status": "success", "message": "Fresh config generated. Restarting..."}
        )

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def check_internet_connectivity() -> bool:
        """Check if internet connectivity is available.

        :return: True if internet is reachable, False otherwise.
        """
        GOOGLE_DNS = "8.8.8.8"
        CLOUDFLARE_DNS = "1.1.1.1"
        DNS_PORT = 53
        TIMEOUT = 5
        try:
            socket.create_connection((GOOGLE_DNS, DNS_PORT), timeout=TIMEOUT)
            return True
        except OSError:
            try:
                socket.create_connection((CLOUDFLARE_DNS, DNS_PORT), timeout=TIMEOUT)
                return True
            except OSError:
                return False
