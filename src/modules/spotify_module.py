import os
from typing import Any, Dict, Optional, Tuple

import spotipy
from loguru import logger

from core.config import Configuration
from enums.variable_importance import Importance

# Constants
REQUESTS_TIMEOUT = 10
VOLUME_INCREMENT = 5


class SpotifyModule:
    def __init__(self) -> None:
        """
        Initialize the SpotifyModule with the given configuration.
        """
        self.enabled: bool = Configuration.read_variable(
            "Modules", "Spotify", "enabled", Importance.REQUIRED
        )
        if not self.enabled:
            logger.info("Disabled")
            return

        logger.debug("Initializing")

        client_id: str = Configuration.read_variable(
            "Modules", "Spotify", "client_id", Importance.REQUIRED
        )
        client_secret: str = Configuration.read_variable(
            "Modules", "Spotify", "client_secret", Importance.REQUIRED
        )
        redirect_uri: str = Configuration.read_variable(
            "Modules", "Spotify", "redirect_uri", Importance.REQUIRED
        )

        try:
            os.environ["SPOTIPY_CLIENT_ID"] = client_id
            os.environ["SPOTIPY_CLIENT_SECRET"] = client_secret
            os.environ["SPOTIPY_REDIRECT_URI"] = redirect_uri

            self.auth_manager = spotipy.SpotifyOAuth(
                scope="user-read-currently-playing, user-read-playback-state, user-modify-playback-state"
            )
            logger.info(
                f"Authorization URL: {self.auth_manager.get_authorize_url()}"
            )
            self.sp = spotipy.Spotify(
                auth_manager=self.auth_manager, requests_timeout=REQUESTS_TIMEOUT
            )
            self.isPlaying: bool = False

            logger.info("Initialized")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            self.enabled = False

    def getCurrentPlayback(self) -> Optional[Tuple[str, str, str, bool, int, int]]:
        """
        Get the current playback information.

        Returns:
            Optional[Tuple[str, str, str, bool, int, int]]: A tuple containing artist, title, art_url, is_playing, progress_ms, and duration_ms.
        """
        if not self.enabled:
            logger.warning("Module is disabled")
            return None

        try:
            track: Dict[str, Any] = self.sp.current_user_playing_track()
            if track and track["item"]:
                artist: str = track["item"]["artists"][0]["name"]
                if len(track["item"]["artists"]) >= 2:
                    artist = f"{artist}, {track['item']['artists'][1]['name']}"
                title: str = track["item"]["name"]
                art_url: str = track["item"]["album"]["images"][0]["url"]
                self.isPlaying = track["is_playing"]
                return (
                    artist,
                    title,
                    art_url,
                    self.isPlaying,
                    track["progress_ms"],
                    track["item"]["duration_ms"],
                )
            else:
                logger.info("No track is currently playing")
                return None
        except Exception as e:
            logger.error(f"Error getting current playback: {e}")
            return None

    def resume_playback(self) -> None:
        """
        Resume playback.
        """
        if self.enabled:
            try:
                self.sp.start_playback()
            except spotipy.exceptions.SpotifyException:
                logger.warning(
                    "No active device, trying specific device"
                )
                devices = self.sp.devices()
                if "devices" in devices and len(devices["devices"]) > 0:
                    try:
                        self.sp.start_playback(device_id=devices["devices"][0]["id"])
                    except Exception as e:
                        logger.error(
                            f"Error resuming playback on specific device: {e}"
                        )
            except Exception as e:
                logger.error(f"Error resuming playback: {e}")

    def pause_playback(self) -> None:
        """
        Pause playback.
        """
        if self.enabled:
            try:
                self.sp.pause_playback()
            except spotipy.exceptions.SpotifyException:
                logger.warning("Problem pausing playback")
            except Exception as e:
                logger.error(f"Error pausing playback: {e}")

    def next_track(self) -> None:
        """
        Skip to the next track.
        """
        if self.enabled:
            try:
                self.sp.next_track()
            except spotipy.exceptions.SpotifyException:
                logger.warning(
                    "No active device, trying specific device"
                )
                devices = self.sp.devices()
                if "devices" in devices and len(devices["devices"]) > 0:
                    self.sp.next_track(device_id=devices["devices"][0]["id"])
            except Exception as e:
                logger.error(f"Error skipping to next track: {e}")

    def previous_track(self) -> None:
        """
        Go to the previous track.
        """
        if self.enabled:
            try:
                self.sp.previous_track()
            except spotipy.exceptions.SpotifyException:
                logger.warning(
                    "No active device, trying specific device"
                )
                devices = self.sp.devices()
                if "devices" in devices and len(devices["devices"]) > 0:
                    self.sp.previous_track(device_id=devices["devices"][0]["id"])
            except Exception as e:
                logger.error(f"Error going to previous track: {e}")

    def increase_volume(self) -> None:
        """
        Increase the volume.
        """
        if self.enabled and self.isPlaying:
            try:
                devices = self.sp.devices()
                curr_volume: int = devices["devices"][0]["volume_percent"]
                self.sp.volume(min(100, curr_volume + VOLUME_INCREMENT))
            except Exception as e:
                logger.error(f"Error increasing volume: {e}")

    def decrease_volume(self) -> None:
        """
        Decrease the volume.
        """
        if self.enabled and self.isPlaying:
            try:
                devices = self.sp.devices()
                curr_volume: int = devices["devices"][0]["volume_percent"]
                self.sp.volume(max(0, curr_volume - VOLUME_INCREMENT))
            except Exception as e:
                logger.error(f"Error decreasing volume: {e}")
            except Exception as e:
                logger.error(f"Error decreasing volume: {e}")
