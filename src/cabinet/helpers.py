"""
A collection of helper functions
"""

import os


def parse_config_bool(value) -> bool:
    """
    Interpret JSON/config values as bool. Handles real booleans, common strings, and empty/missing.
    """
    if value is True or value is False:
        return value
    if value is None or value == "":
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("0", "false", "no", "off", ""):
            return False
        if lowered in ("1", "true", "yes", "on"):
            return True
        return False
    return bool(value)


def resolve_path(path: str) -> str:
    """
    Resolves path aliases and environment variables.

    Args:
        path (str): The path to resolve.

    Returns:
        str: The resolved path.
    """
    return os.path.expanduser(os.path.expandvars(path))
