"""
CyberShield AI — Compatibility Shim
Redirects any imports targeting backend.ml directly to the canonical root ml package.
"""
import sys

try:
    import ml
    sys.modules[__name__] = ml
except ImportError:
    pass
