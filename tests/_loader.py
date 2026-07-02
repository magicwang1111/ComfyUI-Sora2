import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
PACKAGE_NAME = "comfyui_sora2"


def ensure_package_loaded():
    if str(COMFY_ROOT) not in sys.path:
        sys.path.insert(0, str(COMFY_ROOT))
    if PACKAGE_NAME in sys.modules:
        return sys.modules[PACKAGE_NAME]

    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = module
    spec.loader.exec_module(module)
    return module


def import_module(module_name):
    ensure_package_loaded()
    return importlib.import_module(f"{PACKAGE_NAME}.{module_name}")
