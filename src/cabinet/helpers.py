"""
A collection of helper functions
"""

import os

def resolve_path(path: str) -> str:
    """
    Resolves path aliases and environment variables.

    Args:
        path (str): The path to resolve.

    Returns:
        str: The resolved path.
    """
    return os.path.expanduser(os.path.expandvars(path))
