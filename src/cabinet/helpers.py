"""
A collection of helper functions
"""

import os
import pathlib

def resolve_path(path: str) -> str:
    """
    Resolves path aliases and environment variables.

    Args:
        path (str): The path to resolve.

    Returns:
        str: The resolved path.
    """
    expanded_path = os.path.expandvars(path)
    return str(pathlib.Path(expanded_path).expanduser().resolve())
