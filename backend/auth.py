"""Backward-compatible authentication imports.

Authentication implementation lives in the service and presentation layers.
"""

from .presentation.dependencies import (
    create_access_token,
    get_current_identity,
    hash_password,
    require_admin,
    require_participant,
    verify_password,
)

__all__ = [
    "create_access_token",
    "get_current_identity",
    "hash_password",
    "require_admin",
    "require_participant",
    "verify_password",
]
