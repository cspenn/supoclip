# start backend/src/utils/font_options.py
"""Font options parsing and validation utilities.

This module provides utilities for extracting and validating font customization
options from API requests, centralizing this logic that was previously duplicated
across multiple endpoints.
"""

from typing import Any


DEFAULT_FONT_FAMILY = "TikTokSans-Regular"
DEFAULT_FONT_SIZE = 24
DEFAULT_FONT_COLOR = "#FFFFFF"


def parse_font_options(data: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate font options from request data.

    Args:
        data: Request body dictionary that may contain "font_options" key

    Returns:
        Dictionary with font_family, font_size, and font_color keys
        using defaults for any missing values

    Examples:
        >>> parse_font_options({"font_options": {"font_family": "Arial"}})
        {'font_family': 'Arial', 'font_size': 24, 'font_color': '#FFFFFF'}

        >>> parse_font_options({})  # No font options provided
        {'font_family': 'TikTokSans-Regular', 'font_size': 24, 'font_color': '#FFFFFF'}
    """
    font_options = data.get("font_options", {})

    return {
        "font_family": font_options.get("font_family", DEFAULT_FONT_FAMILY),
        "font_size": font_options.get("font_size", DEFAULT_FONT_SIZE),
        "font_color": font_options.get("font_color", DEFAULT_FONT_COLOR),
    }


def merge_with_defaults(
    request_options: dict[str, Any], defaults: dict[str, Any]
) -> dict[str, Any]:
    """Merge request options with defaults, request takes precedence.

    Args:
        request_options: Options from API request (may have None values)
        defaults: Default values to use as fallback

    Returns:
        Merged dictionary where request_options override defaults,
        but None values from request_options are ignored

    Examples:
        >>> merge_with_defaults(
        ...     {"font_family": "Arial", "font_size": None},
        ...     {"font_family": "Default", "font_size": 24}
        ... )
        {'font_family': 'Arial', 'font_size': 24}
    """
    # Start with defaults
    merged = defaults.copy()

    # Override with non-None values from request
    for key, value in request_options.items():
        if value is not None:
            merged[key] = value

    return merged


# end backend/src/utils/font_options.py
