"""
Garmin Connect integration module.
Handles authentication and data fetching from Garmin Connect.
"""

from .adapter import GarminAdapter, MFARequiredError
from .auth import attempt_garmin_login

__all__ = ['GarminAdapter', 'MFARequiredError', 'attempt_garmin_login']
