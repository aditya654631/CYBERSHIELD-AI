import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# Add parent directory (project root) so 'backend', 'ml', 'database' can be imported
if PARENT_DIR and PARENT_DIR != "/" and PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Add current directory to sys.path
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from backend.app.main import app
except ModuleNotFoundError:
    import importlib.util
    app_path = os.path.join(CURRENT_DIR, "app", "main.py")
    spec = importlib.util.spec_from_file_location("cybershield_fastapi_app", app_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cybershield_fastapi_app"] = module
    spec.loader.exec_module(module)
    app = module.app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
