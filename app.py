from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
FE_DIR = ROOT / "front-end"
FE_FILE = FE_DIR / "FrontEndResource.py"

if str(FE_DIR) not in sys.path:
    sys.path.insert(0, str(FE_DIR))

module_globals = runpy.run_path(str(FE_FILE))
app = module_globals.get("app")

if app is None:
    raise RuntimeError("Couldn't find 'app' in front-end/FrontEndResource.py")
