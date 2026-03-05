import copy
import os
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, redirect, render_template, request, url_for
from loguru import logger

from core.app_catalog import APP_CATALOG, CATEGORY_ORDER
from core.config import Configuration
from utils.path import PathTo


class WebServer:
    """Web server for configuring Carousel settings.

    Always-on singleton webserver providing an app-store-style configuration
    interface.  In recovery mode it loads the broken generation for editing.

    Uses a staged-changes pattern: edits are accumulated in ``_pending_changes``
    (server memory only) and written to disk only on explicit user confirmation.
    """

    _instance: Optional["WebServer"] = None

    def __new__(cls) -> "WebServer":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._do_init()
        return cls._instance

    def _do_init(self) -> None:
        """One-time initialization (called from ``__new__``)."""
        self.is_connected = False
        self.lock = threading.Lock()
        self.config_manager = Configuration()
        self.app = Flask(
            __name__,
            template_folder=os.path.join(PathTo.base_directory, PathTo.TEMPLATES_FOLDER),
            static_folder=os.path.join(PathTo.base_directory, PathTo.STATIC_FOLDER),
        )

        self._pending_changes: Dict[str, Dict] = {}

        # In recovery mode: hold the broken config for editing.
        self._recovery_config: Optional[Dict[str, Any]] = (
            self.config_manager.get_broken_generation_for_editing()
            if self.config_manager.is_recovery_mode()
            else None
        )

        self._register_routes()
        self.server_thread = None
        self._server_instance = None

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------

    def _register_routes(self) -> None:
        """Register all routes with the Flask app."""

        # Context processor — available in every template
        @self.app.context_processor
        def inject_globals():
            return {
                "pending_count": len(self._pending_changes),
                "is_recovery_mode": self.config_manager.is_recovery_mode(),
                "categories": CATEGORY_ORDER,
            }

        # Landing
        self.app.add_url_rule("/", "index", self.index)

        # Catalog
        self.app.add_url_rule("/catalog", "catalog", self.catalog)
        self.app.add_url_rule("/catalog/<category>", "catalog", self.catalog)

        # App detail
        self.app.add_url_rule("/app/<app_name>", "app_detail", self.app_detail)

        # Settings
        self.app.add_url_rule("/settings", "settings", self.settings)
        self.app.add_url_rule(
            "/settings/<section>/<subsection>",
            "settings_section",
            self.settings_section,
        )

        # Review
        self.app.add_url_rule("/review", "review_changes", self.review_changes)

        # API endpoints
        self.app.add_url_rule(
            "/api/pending-changes",
            "get_pending_changes",
            self.get_pending_changes,
        )
        self.app.add_url_rule(
            "/api/stage-change",
            "stage_change",
            self.stage_change,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/toggle-app",
            "toggle_app",
            self.toggle_app,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/discard-changes",
            "discard_changes",
            self.discard_changes,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/save-changes",
            "save_changes",
            self.save_changes,
            methods=["POST"],
        )

        # System control (preserved)
        self.app.add_url_rule(
            "/restart", "restart_system", self.restart_system, methods=["POST"]
        )
        self.app.add_url_rule(
            "/close", "close_connection", self.close_connection, methods=["POST"]
        )

        # Recovery mode (preserved)
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

    def _get_live_value(self, path_parts: List[str]) -> Any:
        """Navigate the editable config by path_parts list."""
        node = self._get_editable_config()
        for part in path_parts:
            node = node[part]
        return node

    def _apply_pending_to_config(self, config_copy: Dict) -> Dict:
        """Apply all _pending_changes to a deep copy of the config."""
        for entry in self._pending_changes.values():
            node = config_copy
            for part in entry["path_parts"][:-1]:
                node = node[part]
            node[entry["path_parts"][-1]] = entry["new"]
        return config_copy

    def _get_staged_values_for_app(self, app_name: str) -> Dict[str, Any]:
        """Return {field_key: new_value} for all staged changes under Apps.<app_name>."""
        prefix = f"Apps.{app_name}."
        return {
            k.replace(prefix, ""): v["new"]
            for k, v in self._pending_changes.items()
            if k.startswith(prefix)
        }

    def _get_editable_config(self) -> Dict[str, Any]:
        """Return the config dict that should be presented for editing."""
        if self.config_manager.is_recovery_mode() and self._recovery_config is not None:
            return self._recovery_config
        return self.config_manager.configuration_dictionary

    def _set_editable_config(self, config: Dict[str, Any]) -> None:
        """Persist an in-memory edit back to the appropriate store."""
        if self.config_manager.is_recovery_mode():
            self._recovery_config = config
        else:
            self.config_manager.configuration_dictionary = config

    def _delayed_restart(self, delay: float = 1.0) -> None:
        """Restart the application process after a short delay."""

        def _do():
            time.sleep(delay)
            self.config_manager.restart()

        threading.Thread(target=_do, daemon=True).start()

    # ------------------------------------------------------------------
    # Normal mode routes
    # ------------------------------------------------------------------

    def index(self):
        """Landing / warning page."""
        if self.config_manager.is_recovery_mode():
            return redirect(url_for("recovery_mode_page"))
        with self.lock:
            self.is_connected = True
        return render_template("landing.html")

    def catalog(self, category=None):
        """App store grid — all categories or filtered by one."""
        config = self._get_editable_config()
        apps_config = config.get("Apps", {})

        # Build app list with catalog metadata merged in
        apps = []
        for app_key, app_conf in apps_config.items():
            catalog_entry = APP_CATALOG.get(app_key)
            if catalog_entry is None:
                continue

            if category and catalog_entry.category != category:
                continue

            apps.append({
                "key": app_key,
                "name": catalog_entry.name,
                "description": catalog_entry.description,
                "category": catalog_entry.category,
                "enabled": app_conf.get("enabled", False),
                "order": app_conf.get("order", 999),
            })

        # Sort: enabled apps first (by order), then disabled alphabetically
        apps.sort(key=lambda a: (not a["enabled"], a["order"] if a["enabled"] else a["name"]))

        return render_template(
            "catalog.html",
            apps=apps,
            active_category=category,
        )

    def app_detail(self, app_name):
        """Per-app detail + config editor."""
        catalog_entry = APP_CATALOG.get(app_name)
        if catalog_entry is None:
            return redirect(url_for("catalog"))

        config = self._get_editable_config()
        app_conf = config.get("Apps", {}).get(app_name, {})
        app_config_fields = app_conf.get("config") or {}

        # Check module dependencies
        modules_config = config.get("Modules", {})
        missing_deps = []
        for dep in catalog_entry.dependencies:
            mod = modules_config.get(dep, {})
            if not mod.get("enabled", False):
                missing_deps.append(dep)

        staged = self._get_staged_values_for_app(app_name)

        return render_template(
            "app_detail.html",
            app_key=app_name,
            catalog_entry=catalog_entry,
            app_conf=app_conf,
            app_config_fields=app_config_fields,
            missing_deps=missing_deps,
            staged=staged,
        )

    def settings(self):
        """System config hub — Matrix, Network, Encoder, Tilt, Modules."""
        config = self._get_editable_config()
        system = config.get("System", {})
        modules = config.get("Modules", {})

        return render_template("settings.html", system=system, modules=modules)

    def settings_section(self, section, subsection):
        """Subsection form editor for system settings."""
        config = self._get_editable_config()

        section_data = config.get(section, {})
        subsection_data = section_data.get(subsection)
        if subsection_data is None:
            return redirect(url_for("settings"))

        # Build staged values for this section
        prefix = f"{section}.{subsection}."
        staged = {
            k.replace(prefix, ""): v["new"]
            for k, v in self._pending_changes.items()
            if k.startswith(prefix)
        }

        return render_template(
            "settings_section.html",
            section=section,
            subsection=subsection,
            fields=subsection_data,
            staged=staged,
        )

    def review_changes(self):
        """Diff view of all pending changes."""
        changes = list(self._pending_changes.values())

        # Group by display_path
        grouped: Dict[str, list] = {}
        for change in changes:
            dp = change.get("display_path", "")
            grouped.setdefault(dp, []).append(change)

        next_gen = self._get_editable_config().get("Metadata", {}).get("id", 0) + 1

        return render_template(
            "review_changes.html",
            changes=changes,
            grouped=grouped,
            next_gen=next_gen,
        )

    # ------------------------------------------------------------------
    # API endpoints
    # ------------------------------------------------------------------

    def get_pending_changes(self):
        """Return pending changes as JSON."""
        return jsonify({
            "count": len(self._pending_changes),
            "changes": list(self._pending_changes.values()),
        })

    def stage_change(self):
        """Stage one field change."""
        data = request.get_json(silent=True) or {}
        path = data.get("path", "")
        new_value = data.get("new_value")

        if not path:
            return jsonify({"status": "error", "message": "Missing path"}), 400

        path_parts = path.split(".")
        try:
            old_value = self._get_live_value(path_parts)
        except (KeyError, TypeError) as e:
            return jsonify({"status": "error", "message": f"Invalid path: {e}"}), 400

        # Type coercion
        if isinstance(old_value, bool):
            if isinstance(new_value, str):
                new_value = new_value.lower() == "true"
            else:
                new_value = bool(new_value)
            val_type = "bool"
        elif isinstance(old_value, int):
            new_value = int(new_value)
            val_type = "int"
        elif isinstance(old_value, float):
            new_value = float(new_value)
            val_type = "float"
        elif old_value is None:
            val_type = "null"
        else:
            new_value = str(new_value) if new_value is not None else ""
            val_type = "str"

        # If reverted to original, remove from pending
        if new_value == old_value:
            self._pending_changes.pop(path, None)
        else:
            section = path_parts[0] if len(path_parts) > 0 else ""
            subsection = path_parts[1] if len(path_parts) > 1 else ""
            label = path_parts[-1]
            display_path = " › ".join(path_parts[:-1])

            self._pending_changes[path] = {
                "path": path,
                "path_parts": path_parts,
                "section": section,
                "subsection": subsection,
                "label": label,
                "display_path": display_path,
                "old": old_value,
                "new": new_value,
                "type": val_type,
            }

        return jsonify({"status": "ok", "pending_count": len(self._pending_changes)})

    def toggle_app(self):
        """Toggle app enabled/disabled — shorthand for stage_change."""
        data = request.get_json(silent=True) or {}
        app_key = data.get("app_key", "")

        if not app_key:
            return jsonify({"status": "error", "message": "Missing app_key"}), 400

        path = f"Apps.{app_key}.enabled"
        path_parts = path.split(".")

        try:
            current = self._get_live_value(path_parts)
        except (KeyError, TypeError):
            return jsonify({"status": "error", "message": f"App '{app_key}' not found"}), 404

        new_value = not current
        # Check if there's already a staged change — if so, the effective value differs
        if path in self._pending_changes:
            staged_val = self._pending_changes[path]["new"]
            new_value = not staged_val

        # Delegate to stage_change logic
        if new_value == current:
            self._pending_changes.pop(path, None)
        else:
            self._pending_changes[path] = {
                "path": path,
                "path_parts": path_parts,
                "section": "Apps",
                "subsection": app_key,
                "label": "enabled",
                "display_path": f"Apps › {app_key}",
                "old": current,
                "new": new_value,
                "type": "bool",
            }

        return jsonify({
            "status": "ok",
            "pending_count": len(self._pending_changes),
            "new_enabled": new_value,
        })

    def discard_changes(self):
        """Clear all staged changes."""
        self._pending_changes.clear()
        return jsonify({"status": "ok", "pending_count": 0})

    def save_changes(self):
        """Apply staged changes, create new generation, restart."""
        if not self._pending_changes:
            return jsonify({"status": "error", "message": "No pending changes"}), 400

        config_copy = copy.deepcopy(self._get_editable_config())
        self._apply_pending_to_config(config_copy)

        # In recovery mode the base config carries is_broken=True — strip it so
        # the new generation is treated as a healthy config on next boot.
        if self.config_manager.is_recovery_mode():
            config_copy.setdefault("Metadata", {})["is_broken"] = False
            config_copy["Metadata"]["broken_reason"] = None

        try:
            if not self.config_manager.create_new_config_generation(config_copy):
                return jsonify({
                    "status": "error",
                    "message": "Failed to save configuration.",
                }), 500
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Validation failed: {e}",
            }), 422

        gen_id = config_copy.get("Metadata", {}).get("id", "?")
        self._pending_changes.clear()
        self._delayed_restart()
        return jsonify({
            "status": "success",
            "message": f"Configuration saved as generation {gen_id}. Restarting...",
        })

    # ------------------------------------------------------------------
    # System control (preserved)
    # ------------------------------------------------------------------

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

    def start(self, port: int, debug: bool = False) -> threading.Thread:
        """Start the web server in a background daemon thread."""

        def run_server():
            host = "0.0.0.0"
            if debug:
                logger.warning("Starting Flask development server (debug mode enabled)")
                from werkzeug.serving import make_server

                server = make_server(host, port, self.app)
                self._server_instance = server
                server.serve_forever()
                return

            try:
                from waitress import create_server

                logger.info("Starting Waitress production server")
                server = create_server(
                    self.app,
                    host=host,
                    port=port,
                    threads=2,
                    connection_limit=20,
                    channel_timeout=30,
                    cleanup_interval=15,
                )
                self._server_instance = server
                server.run()
            except ModuleNotFoundError:
                logger.error(
                    "Waitress is not installed; falling back to Flask development server. "
                    "Install dependencies to use production server mode."
                )
                from werkzeug.serving import make_server

                server = make_server(host, port, self.app)
                self._server_instance = server
                server.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"Web server started on port {port}")
        return self.server_thread

    def stop(self) -> None:
        """Shut down the server and release the port."""
        if self._server_instance is None:
            return
        try:
            self._server_instance.shutdown()  # werkzeug BaseWSGIServer
        except AttributeError:
            try:
                self._server_instance.close()  # waitress TcpWSGIServer
            except Exception as e:
                logger.warning(f"Failed to close server socket: {e}")
        self._server_instance = None
        logger.info("Web server stopped.")

    # ------------------------------------------------------------------
    # Recovery mode routes (preserved)
    # ------------------------------------------------------------------

    def recovery_mode_page(self):
        """Dedicated recovery mode page."""
        if not self.config_manager.is_recovery_mode():
            return redirect(url_for("catalog"))

        info = self.config_manager.get_recovery_mode_info() or {}
        reason = info.get("reason", "Unknown critical error")
        broken_id = info.get("broken_generation_id", 0)
        timestamp = info.get("timestamp", "")

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
        """Apply the (edited) broken config as a new working generation."""
        if not self.config_manager.is_recovery_mode():
            return jsonify({"status": "error", "message": "Not in recovery mode"}), 400

        if self._recovery_config is None:
            return jsonify({
                "status": "error",
                "message": "No recovery config available to apply",
            }), 400

        logger.info("Recovery mode: applying fixed config as new generation")

        if not self.config_manager.apply_recovery_config(self._recovery_config):
            return jsonify({
                "status": "error",
                "message": "Config validation failed — fix the remaining errors before applying",
            }), 422

        if not self.config_manager.clear_recovery_mode():
            return jsonify({
                "status": "error",
                "message": "Config saved but failed to clear recovery mode trigger",
            }), 500

        self._delayed_restart()
        return jsonify(
            {"status": "success", "message": "Fixed config applied. Restarting..."}
        )

    def recovery_mode_rollback(self):
        """Restore the previous working generation and exit recovery mode."""
        if not self.config_manager.is_recovery_mode():
            return jsonify({"status": "error", "message": "Not in recovery mode"}), 400

        prev_id = self.config_manager.get_latest_working_generation_id()
        if prev_id <= 0:
            return jsonify({
                "status": "error",
                "message": "No previous working generation found",
            }), 404

        logger.info(f"Recovery mode: rolling back to generation {prev_id}")

        if not self.config_manager.clear_recovery_mode():
            return jsonify({
                "status": "error",
                "message": "Failed to clear recovery mode trigger",
            }), 500

        self._delayed_restart()
        return jsonify({
            "status": "success",
            "message": f"Restoring generation {prev_id}. Restarting...",
        })

    def recovery_mode_generate_new(self):
        """Generate a fresh config from the template and exit recovery mode."""
        if not self.config_manager.is_recovery_mode():
            return jsonify({"status": "error", "message": "Not in recovery mode"}), 400

        logger.info("Recovery mode: generating fresh config from template")

        try:
            self.config_manager.create_new_configuration_from_template()
        except SystemExit:
            return jsonify({
                "status": "error",
                "message": "Failed to generate config from template",
            }), 500

        if not self.config_manager.clear_recovery_mode():
            return jsonify({
                "status": "error",
                "message": "Config generated but failed to clear recovery mode trigger",
            }), 500

        self._delayed_restart()
        return jsonify(
            {"status": "success", "message": "Fresh config generated. Restarting..."}
        )

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def check_internet_connectivity() -> bool:
        """Check if internet connectivity is available."""
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
