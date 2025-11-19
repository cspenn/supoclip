# start backend/src/services/user_preferences_service.py

"""User preferences service.

Centralizes user preference loading, merging with request options,
and default handling. Eliminates duplicated preference logic across endpoints.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class UserPreferencesService:
    """Service for managing user preferences.

    Centralizes preference loading, merging, and default handling.
    Implements the priority: Request options > User preferences > System defaults
    """

    # System-wide default preferences
    DEFAULT_PREFERENCES = {
        "font_family": "TikTokSans-Regular",
        "font_size": 24,
        "font_color": "#FFFFFF",
        "clip_min_length": 10,
        "clip_target_length": 30,
        "clip_max_length": 45,
        "custom_ai_prompt": None,
        "logo_file_path": None,
        "logo_corner_position": "top-right",
        "output_resolution": "720p",
    }

    # Mapping from preference keys to database column names
    PREFERENCE_FIELDS = {
        "font_family": "default_font_family",
        "font_size": "default_font_size",
        "font_color": "default_font_color",
        "clip_min_length": "default_clip_min_length",
        "clip_target_length": "default_clip_target_length",
        "clip_max_length": "default_clip_max_length",
        "custom_ai_prompt": "custom_ai_prompt",
        "logo_file_path": "logo_file_path",
        "logo_corner_position": "logo_corner_position",
        "output_resolution": "output_resolution",
    }

    def __init__(self, db: AsyncSession):
        """Initialize user preferences service.

        Args:
            db: Database session for querying user preferences
        """
        self.db = db

    def _merge_with_defaults(self, user_prefs_row) -> dict[str, Any]:
        """Merge user preferences with defaults using field mapping.

        Args:
            user_prefs_row: Database row containing user preferences

        Returns:
            Dictionary with user preferences merged with defaults
        """
        preferences = {}
        for key, db_column in self.PREFERENCE_FIELDS.items():
            user_value = (
                getattr(user_prefs_row, db_column, None) if user_prefs_row else None
            )
            preferences[key] = user_value or self.DEFAULT_PREFERENCES[key]
        return preferences

    async def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """Load user preferences from database.

        Merges user-stored preferences with system defaults.
        User preferences take precedence over system defaults.

        Args:
            user_id: User ID to load preferences for

        Returns:
            Dictionary of user preferences merged with defaults

        Raises:
            ValueError: If user not found in database
        """
        result = await self.db.execute(
            text(
                """
                SELECT default_font_family, default_font_size, default_font_color,
                       default_clip_min_length, default_clip_target_length,
                       default_clip_max_length, custom_ai_prompt,
                       logo_file_path, logo_corner_position
                FROM users WHERE id = :user_id
            """
            ),
            {"user_id": user_id},
        )
        user_prefs = result.fetchone()

        if not user_prefs:
            logger.error(f"User {user_id} not found in database")
            raise ValueError(f"User not found: {user_id}")

        logger.info(f"Loaded preferences for user {user_id}")

        return self._merge_with_defaults(user_prefs)

    async def merge_with_request_options(
        self, user_id: str, request_options: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge request options with user preferences and system defaults.

        Priority order (highest to lowest):
        1. Request options (if provided and not default values)
        2. User preferences (from database)
        3. System defaults

        Args:
            user_id: User ID to load preferences for
            request_options: Options from API request (may contain None values)

        Returns:
            Merged dictionary with all preferences resolved

        Raises:
            ValueError: If user not found in database
        """
        # Load user preferences (already merged with system defaults)
        user_prefs = await self.get_user_preferences(user_id)

        # Merge with request options (request options take precedence)
        merged = user_prefs.copy()

        # Override with request options if they differ from system defaults
        # This ensures explicit request values override user prefs
        for key in ["font_family", "font_size", "font_color"]:
            if key in request_options:
                request_value = request_options[key]
                default_value = self.DEFAULT_PREFERENCES[key]
                # Only override if request explicitly changed from default
                if request_value != default_value:
                    merged[key] = request_value

        # Override clip settings if provided
        for key in [
            "clip_min_length",
            "clip_target_length",
            "clip_max_length",
            "custom_ai_prompt",
        ]:
            if key in request_options and request_options[key] is not None:
                merged[key] = request_options[key]

        logger.info(
            f"Merged preferences for user {user_id}: font={merged['font_family']}, size={merged['font_size']}"
        )

        return merged

    def get_logo_path(self, preferences: dict[str, Any]) -> Optional[Path]:
        """Extract logo path from preferences.

        Args:
            preferences: Merged preferences dictionary

        Returns:
            Path object if logo configured, None otherwise
        """
        logo_file_path = preferences.get("logo_file_path")
        return Path(logo_file_path) if logo_file_path else None


# end backend/src/services/user_preferences_service.py
