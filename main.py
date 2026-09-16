import os
import sys

# Ensure the repository root stays ahead of the legacy backend directory.
# Canonical packages such as ``database`` and ``ml`` live at the root; putting
# ``backend`` first makes their compatibility shims shadow those packages and
# causes circular imports in clean production processes.
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

for p in [BACKEND_DIR, ROOT_DIR]:
    if p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, ROOT_DIR)

from backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
