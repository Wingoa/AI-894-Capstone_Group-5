"""Expose source modules under data_model/src/data_model as data_model.* imports."""

from pathlib import Path


_pkg_root = Path(__file__).resolve().parent
_src_pkg = _pkg_root / "src" / "data_model"

# Keep existing package path entries and add src/data_model for runtime imports.
if _src_pkg.is_dir():
    __path__.append(str(_src_pkg))
