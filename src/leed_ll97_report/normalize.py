"""
Address and field normalization for building records.

Uses usaddress for parsing and applies standard suffix mappings,
punctuation cleanup, and borough normalization.
"""

import logging
import re
from typing import Any

import usaddress

logger = logging.getLogger(__name__)

# ── Street suffix standardization (USPS Publication 28) ────────────────────
SUFFIX_MAP = {
    "avenue": "AVE", "ave": "AVE", "av": "AVE",
    "boulevard": "BLVD", "blvd": "BLVD",
    "circle": "CIR", "cir": "CIR",
    "court": "CT", "ct": "CT",
    "drive": "DR", "dr": "DR",
    "expressway": "EXPY", "expy": "EXPY",
    "highway": "HWY", "hwy": "HWY",
    "lane": "LN", "ln": "LN",
    "parkway": "PKWY", "pkwy": "PKWY",
    "place": "PL", "pl": "PL",
    "plaza": "PLZ", "plz": "PLZ",
    "road": "RD", "rd": "RD",
    "square": "SQ", "sq": "SQ",
    "street": "ST", "st": "ST", "str": "ST",
    "terrace": "TER", "ter": "TER",
    "turnpike": "TPKE", "tpke": "TPKE",
    "way": "WAY",
}

# ── Directional standardization ───────────────────────────────────────────
DIRECTION_MAP = {
    "north": "N", "south": "S", "east": "E", "west": "W",
    "northeast": "NE", "northwest": "NW",
    "southeast": "SE", "southwest": "SW",
    "n": "N", "s": "S", "e": "E", "w": "W",
    "ne": "NE", "nw": "NW", "se": "SE", "sw": "SW",
}

# ── Borough normalization ─────────────────────────────────────────────────
BOROUGH_MAP = {
    "manhattan": "MANHATTAN",
    "new york": "MANHATTAN",
    "ny": "MANHATTAN",
    "bronx": "BRONX",
    "the bronx": "BRONX",
    "bx": "BRONX",
    "brooklyn": "BROOKLYN",
    "bk": "BROOKLYN",
    "kings": "BROOKLYN",
    "queens": "QUEENS",
    "qn": "QUEENS",
    "staten island": "STATEN ISLAND",
    "si": "STATEN ISLAND",
    "richmond": "STATEN ISLAND",
}

# Ordinal number normalization (1st → 1, 2nd → 2, etc.)
_ORDINAL_RE = re.compile(r"(\d+)\s*(st|nd|rd|th)\b", re.IGNORECASE)

# Unit / suite / floor removal
_UNIT_RE = re.compile(
    r"\b(suite|ste|unit|apt|apartment|floor|fl|rm|room|#)\s*[\w\-]*",
    re.IGNORECASE,
)


def normalize_address(raw: Any) -> str:
    """
    Normalize a raw address string for matching.

    Steps:
    1. Uppercase
    2. Remove punctuation
    3. Remove unit/suite/floor designators
    4. Standardize ordinals
    5. Parse with usaddress
    6. Standardize suffixes and directions
    7. Reassemble
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""

    addr = raw.strip().upper()

    # Remove punctuation except hyphens (keep for addresses like 123-45)
    addr = re.sub(r"[.,;:!?()\"']", "", addr)

    # Remove unit designators
    addr = _UNIT_RE.sub("", addr)

    # Normalize ordinals: 42ND → 42
    addr = _ORDINAL_RE.sub(r"\1", addr)

    # Collapse whitespace
    addr = re.sub(r"\s+", " ", addr).strip()

    # Parse with usaddress
    try:
        parsed, addr_type = usaddress.tag(addr)
    except usaddress.RepeatedLabelError:
        # Fallback: just do basic suffix replacement
        return _fallback_normalize(addr)

    # Standardize street suffix
    suffix = parsed.get("StreetNamePostType", "")
    if suffix.lower() in SUFFIX_MAP:
        parsed["StreetNamePostType"] = SUFFIX_MAP[suffix.lower()]

    # Standardize direction prefix/suffix
    for key in ("StreetNamePreDirectional", "StreetNamePostDirectional"):
        direction = parsed.get(key, "")
        if direction.lower() in DIRECTION_MAP:
            parsed[key] = DIRECTION_MAP[direction.lower()]

    # Reassemble in order: number, pre-direction, name, suffix, post-direction
    parts = []
    for component in [
        "AddressNumber",
        "StreetNamePreDirectional",
        "StreetName",
        "StreetNamePostType",
        "StreetNamePostDirectional",
    ]:
        val = parsed.get(component, "").strip()
        if val:
            parts.append(val)

    return " ".join(parts) if parts else addr


def _fallback_normalize(addr: str) -> str:
    """Simple normalization when usaddress parsing fails."""
    words = addr.split()
    normalized = []
    for w in words:
        wl = w.lower()
        if wl in SUFFIX_MAP:
            normalized.append(SUFFIX_MAP[wl])
        elif wl in DIRECTION_MAP:
            normalized.append(DIRECTION_MAP[wl])
        else:
            normalized.append(w)
    return " ".join(normalized)


def normalize_borough(raw: Any) -> str:
    """Normalize borough / city name to standard uppercase form."""
    if not isinstance(raw, str) or not raw.strip():
        return ""
    key = raw.strip().lower()
    return BOROUGH_MAP.get(key, raw.strip().upper())


def normalize_zip(raw: Any) -> str:
    """Normalize ZIP code to 5-digit string."""
    if not raw:
        return ""
    z = str(raw).strip().split("-")[0].split(".")[0]
    # Remove non-digits
    z = re.sub(r"\D", "", z)
    if len(z) == 5:
        return z
    if len(z) > 5:
        return z[:5]
    return z.zfill(5) if z else ""


def normalize_building_name(raw: Any) -> str:
    """Normalize building name for fuzzy matching."""
    if not isinstance(raw, str) or not raw.strip():
        return ""
    name = raw.strip().upper()
    # Remove punctuation
    name = re.sub(r"[.,;:!?()\"'\-/]", " ", name)
    # Remove common filler words
    for filler in ["THE", "BUILDING", "BLDG", "AT", "OF"]:
        name = re.sub(rf"\b{filler}\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_bbl(raw: Any) -> str:
    """Normalize BBL (Borough-Block-Lot) to 10-digit string."""
    if not raw:
        return ""
    bbl = re.sub(r"\D", "", str(raw).strip())
    if len(bbl) == 10:
        return bbl
    return bbl if bbl else ""


def normalize_bin(raw: Any) -> str:
    """Normalize BIN (Building Identification Number) to 7-digit string."""
    if not raw:
        return ""
    b = re.sub(r"\D", "", str(raw).strip().split(".")[0])
    if len(b) == 7:
        return b
    return b if b else ""
