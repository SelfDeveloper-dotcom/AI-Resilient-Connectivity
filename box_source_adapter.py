"""Optional future Box SRC adapter.

The active prototype uses the local directory SRC. This adapter is intentionally
isolated so Box can replace the source without changing Collector/PP/ML layers.
Install optional dependencies from requirements-box.txt and provide Box app
credentials only when the Box source is ready. Never commit credentials.
"""
from __future__ import annotations
from pathlib import Path

class BoxSourceNotConfigured(RuntimeError): pass

class BoxSourceAdapter:
    def __init__(self,*args,**kwargs):
        try:
            import boxsdk  # noqa: F401
        except ImportError as e:
            raise BoxSourceNotConfigured("Box SDK is not installed. Use requirements-box.txt when Box is ready.") from e
        raise BoxSourceNotConfigured("Box source is scaffolded but intentionally disabled until Box application credentials/folder IDs are configured.")
