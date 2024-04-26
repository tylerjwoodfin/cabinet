"""
A collection of helper functions
"""

import os

def resolve_path(path: str) -> str:
    """
    resolves path aliases and environment variables.

    args:
        path (str): the path to resolve.

    returns:
        the resolved path.
    """
    return os.path.expanduser(os.path.expandvars(path))
