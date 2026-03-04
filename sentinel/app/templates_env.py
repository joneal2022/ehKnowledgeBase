"""Jinja2Templates singleton — import from here to avoid circular imports."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
