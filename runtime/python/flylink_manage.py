import os, sys, runpy
from pathlib import Path

# Resolve backend next to package root: .../runtime/python/flylink_manage.py -> .../backend
here = Path(__file__).resolve().parent
root = here.parent.parent
backend = Path(os.environ.get("FLYLINK_BACKEND") or (root / "backend"))
backend = backend.resolve()

if not backend.exists():
    raise SystemExit(f"Backend not found: {backend}")

os.chdir(backend)
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))
os.environ["FLYLINK_BACKEND"] = str(backend)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Keep only manage.py args
argv_tail = sys.argv[1:]
sys.argv = [str(backend / "manage.py")] + argv_tail
runpy.run_path(str(backend / "manage.py"), run_name="__main__")
