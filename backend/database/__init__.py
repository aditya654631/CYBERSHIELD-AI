"""
CyberShield AI — Compatibility Shim
Redirects any imports targeting backend.database directly to the canonical root database package.
"""
import sys

try:
    import database
    sys.modules[__name__] = database
except ImportError:
    pass
