"""
Compatibility shim forwarding backend.database.seed to canonical database.seed.
"""
import sys
try:
    import database.seed
    sys.modules[__name__] = database.seed
except ImportError:
    pass
