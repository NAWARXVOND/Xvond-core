import importlib
import inspect
import logging
import pkgutil

from backend.app.core.config.settings import settings
from backend.app.core.module import BaseModule

logger = logging.getLogger("xvond.modules")


def discover_modules(strict: bool | None = None):
    strict_mode = settings.is_production if strict is None else bool(strict)
    discovered = []
    failures = []

    package_name = "backend.app.modules"
    package = importlib.import_module(package_name)

    for module_info in pkgutil.iter_modules(package.__path__):
        module_name = module_info.name

        if module_name.startswith("_"):
            continue
        if settings.is_production and module_name == "test_module":
            continue

        try:
            imported = importlib.import_module(f"{package_name}.{module_name}")
        except Exception as exc:
            failures.append(
                {
                    "module": module_name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue

        for _, cls in inspect.getmembers(imported, inspect.isclass):
            if issubclass(cls, BaseModule) and cls is not BaseModule:
                discovered.append(cls())

    if failures:
        detail = "; ".join(
            f"{item['module']}: {item['error_type']}: {item['error']}"
            for item in failures
        )
        if strict_mode:
            raise RuntimeError(
                "Xvond module discovery failed; refusing partial startup: " + detail
            )
        logger.warning("Some optional modules could not be loaded: %s", detail)

    return discovered
