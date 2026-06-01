from dataclasses import dataclass
from typing import Literal, Optional

Source = Literal["geometry", "font_flag", "vlm", "ocr"]


@dataclass
class Span:
    """One run of text with its detected formatting and provenance."""
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    bold: bool = False
    italic: bool = False
    struck: bool = False
    underlined: bool = False
    confidence: float = 1.0
    source: Source = "geometry"
    flag_reason: Optional[str] = None
