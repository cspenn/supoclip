# start src/exceptions.py
"""Centralized exception hierarchy for SupoClip.

All domain-specific errors derive from :class:`SupoClipError` so callers can
catch the whole family with a single ``except SupoClipError`` while still being
able to discriminate on the concrete subclass. Pipeline modules re-export their
historical names (``AnalysisError``, ``DownloadError`` …) as subclasses of these
base types to preserve backwards-compatible ``except`` sites.
"""

from __future__ import annotations


class SupoClipError(Exception):
    """Base class for every error raised by SupoClip's own code."""


class DownloadError(SupoClipError):
    """Raised when video acquisition (yt-dlp / upload) fails."""


class TranscriptionError(SupoClipError):
    """Raised when audio transcription fails."""


class AnalysisError(SupoClipError):
    """Raised when LLM transcript analysis fails."""


class InsufficientSegmentsError(AnalysisError):
    """Raised when analysis yields fewer than one usable clip segment."""


class ClipGenerationError(SupoClipError):
    """Raised when ffmpeg clip generation fails."""


class ConfigurationError(SupoClipError):
    """Raised when required configuration is missing or invalid."""
