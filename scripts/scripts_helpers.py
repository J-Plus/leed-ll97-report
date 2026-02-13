"""
Shared helpers for pipeline scripts.
Keeps sys.path wiring and logging setup in one place.
"""

import logging
import sys
from pathlib import Path

# Ensure project root is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))


def get_config():
    """Import and return the config module."""
    import scripts.s00_config as cfg
    return cfg


def setup_logging(level=logging.INFO):
    """Configure root logger."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# Re-export config as a module-level convenience
def _load_config():
    """Lazy-load config to avoid import-time side effects."""
    _scripts = Path(__file__).resolve().parent
    _root = _scripts.parent
    sys.path.insert(0, str(_scripts))
    sys.path.insert(0, str(_root / "src"))

    # Use importlib to load 00_config.py which has a leading digit
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", _scripts / "00_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_config():
    """Return the config module."""
    return _load_config()
