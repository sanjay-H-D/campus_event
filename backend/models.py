"""Backward-compatible model imports.

New code should import models from ``backend.database.models``.
"""

from .database.models import Admin, Booking, College, Event, Payment, Student

__all__ = ["Admin", "Booking", "College", "Event", "Payment", "Student"]
