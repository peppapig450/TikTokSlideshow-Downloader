"""Extractor package exports."""

from .base import BaseExtractor
from .slideshow import SlideshowExtractor, SlideshowResult

__all__ = ["BaseExtractor", "SlideshowExtractor", "SlideshowResult"]
