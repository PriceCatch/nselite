"""NSE hosts. Override with environment variables if NSE moves domains again."""

import os

NSE_HOST = os.environ.get("NSE_HOST", "https://www.nseindia.in").rstrip("/")
ARCHIVES_HOST = os.environ.get("NSE_ARCHIVES_HOST", "https://nsearchives.nseindia.in").rstrip("/")
API_BASE = f"{NSE_HOST}/api"
