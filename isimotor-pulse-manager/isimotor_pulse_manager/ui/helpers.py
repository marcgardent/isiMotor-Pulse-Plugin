"""
Rate conversion and configuration form helpers.
"""

from typing import Any


def parse_rate_to_mode_and_hz(val: Any, default_hz: str = "5") -> tuple[str, str]:
    """Parses a rate string (e.g. 'unlimited', '60Hz', 'off', '0') into (mode: 'unlimited'|'limited'|'off', hz_num: str)."""
    s = str(val).strip().lower()
    clean_def = default_hz.lower().replace("hz", "").strip() or "5"
    if s in ["unlimited", "max", "none", ""]:
        return "unlimited", clean_def
    elif s in ["off", "disabled", "0", "0hz"]:
        return "off", clean_def
    else:
        num = s.replace("hz", "").strip()
        return "limited", (num if num else clean_def)


def format_mode_and_hz_to_rate(mode: str, hz_val: str, default_hz: str = "5") -> str:
    """Converts (mode, hz_val) to the string format expected by CustomPluginVariables.JSON."""
    if mode == "unlimited":
        return "unlimited"
    elif mode == "off":
        return "off"
    else:
        clean_num = str(hz_val).strip().lower().replace("hz", "").strip()
        if not clean_num:
            clean_num = default_hz.lower().replace("hz", "").strip() or "5"
        return f"{clean_num}Hz"
