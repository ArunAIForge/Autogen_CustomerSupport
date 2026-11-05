"""Bootstrap loader for ClothesSpot environment.

Ensures seamless direct module discovery and path resolution across all
container, local, and virtualized 9p filesystem environments.
"""

import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path


class DirectModuleFinder(importlib.abc.MetaPathFinder):
    """Direct path resolution MetaPathFinder that checks files directly."""

    def __init__(self, root_dirs=None):
        if root_dirs:
            self.root_dirs = [Path(d).resolve() for d in root_dirs]
        else:
            self.root_dirs = [
                Path("/working_dir/c_cb662a17c1cb7f7c").resolve(),
                Path("/working_dir/c_cb662a17c1cb7f7c/backend").resolve(),
                Path(os.getcwd()).resolve(),
            ]

    def find_spec(self, fullname, path, target=None):
        parts = fullname.split(".")
        for root in self.root_dirs:
            # Check module: root/pkg/mod.py
            mod_file = root.joinpath(*parts).with_suffix(".py")
            if mod_file.is_file():
                return importlib.util.spec_from_file_location(fullname, str(mod_file))

            # Check package: root/pkg/__init__.py
            pkg_dir = root.joinpath(*parts)
            init_file = pkg_dir / "__init__.py"
            if pkg_dir.is_dir() and init_file.is_file():
                return importlib.util.spec_from_file_location(
                    fullname, str(init_file), submodule_search_locations=[str(pkg_dir)]
                )
        return None


# Insert into sys.meta_path if not already registered
_ws_root = Path("/working_dir/c_cb662a17c1cb7f7c").resolve()
if str(_ws_root) not in sys.path:
    sys.path.insert(0, str(_ws_root))

if not any(isinstance(finder, DirectModuleFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, DirectModuleFinder([_ws_root, _ws_root / "backend"]))
