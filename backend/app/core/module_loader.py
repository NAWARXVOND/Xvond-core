import importlib
import inspect
import pkgutil

from backend.app.core.module import BaseModule
from backend.app.core.config.settings import settings


def discover_modules():
    discovered = []

    package_name = "backend.app.modules"

    package = importlib.import_module(
        package_name
    )

    for module_info in pkgutil.iter_modules(
        package.__path__
    ):
        module_name = module_info.name

        if module_name.startswith("_"):
            continue

        if (
            settings.is_production
            and module_name == "test_module"
        ):
            continue

        try:
            imported = importlib.import_module(
                f"{package_name}.{module_name}"
            )

        except Exception as exc:
            print(
                f"Could not load module "
                f"'{module_name}': {exc}"
            )
            continue

        for _, cls in inspect.getmembers(
            imported,
            inspect.isclass,
        ):
            if (
                issubclass(cls, BaseModule)
                and cls is not BaseModule
            ):
                discovered.append(
                    cls()
                )

    return discovered
