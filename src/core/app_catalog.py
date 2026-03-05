"""Static app catalog — developer-maintained metadata for all Carousel apps.

This module separates app declaration (what an app IS) from user configuration
(what the user CHOSE). The frozen dataclass entries are the source of truth for
display names, descriptions, categories, orientations, and module dependencies.

No imports from the rest of the codebase — this is a pure data module.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class AppEntry:
    name: str
    description: str
    category: str
    orientations: List[str]
    dependencies: List[str] = field(default_factory=list)


APP_CATALOG: Dict[str, AppEntry] = {
    "MainScreen": AppEntry(
        name="Main Screen",
        description="Clock and date display with multiple themes.",
        category="Top",
        orientations=["horizontal", "vertical"],
    ),
    "GifPlayer": AppEntry(
        name="GIF Player",
        description="Plays animated GIFs from the data/gifs directory.",
        category="Entertainment",
        orientations=["horizontal", "vertical"],
    ),
    "Pomodoro": AppEntry(
        name="Pomodoro",
        description="Focus timer with work/break cycles.",
        category="Productivity",
        orientations=["horizontal", "vertical"],
    ),
    "GameOfLife": AppEntry(
        name="Game of Life",
        description="Conway's Game of Life cellular automaton.",
        category="Games",
        orientations=["horizontal", "vertical"],
    ),
    "Spotify": AppEntry(
        name="Spotify",
        description="Now-playing display for Spotify.",
        category="Music",
        orientations=["horizontal"],
        dependencies=["Spotify"],
    ),
    "Notion": AppEntry(
        name="Notion",
        description="Displays tasks from a Notion database.",
        category="Productivity",
        orientations=["horizontal"],
        dependencies=["Notion"],
    ),
    "Youtube": AppEntry(
        name="YouTube",
        description="Subscriber count display.",
        category="Social",
        orientations=["horizontal"],
        dependencies=["Youtube"],
    ),
    "Pushbullet": AppEntry(
        name="Pushbullet",
        description="Push notification display.",
        category="Notifications",
        orientations=["horizontal"],
        dependencies=["Pushbullet"],
    ),
    "Weather": AppEntry(
        name="Weather",
        description="Current conditions and forecast.",
        category="Info",
        orientations=["horizontal", "vertical"],
        dependencies=["Weather"],
    ),
}

CATEGORY_ORDER: List[str] = [
    "Top",
    "Entertainment",
    "Productivity",
    "Games",
    "Music",
    "Social",
    "Notifications",
    "Info",
]
