import os
import sys
import types

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# Add parent directory (project root) so 'backend', 'ml', 'database' can be imported if running from root
if PARENT_DIR and PARENT_DIR != "/" and PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Add current directory to sys.path
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# If 'backend' package cannot be found (e.g. Railway Root Directory set to backend),
# alias 'backend' to CURRENT_DIR so 'from backend.app...' imports work transparently
if "backend" not in sys.modules:
    try:
        import backend
    except ModuleNotFoundError:
        backend_pkg = types.ModuleType("backend")
        backend_pkg.__path__ = [CURRENT_DIR]
        sys.modules["backend"] = backend_pkg

from backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
