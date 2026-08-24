from backend.app.core.module import BaseModule
from backend.app.core.module_registry import module_registry


class ModuleManager:

    def __init__(self):
        self._status: dict[str, str] = {}

    def install(
        self,
        module: BaseModule,
    ):
        module_registry.register(
            module
        )

        if module.name not in self._status:
            self._status[module.name] = "installed"

    def enable(
        self,
        name: str,
    ):
        module = module_registry.get(
            name
        )

        if module is None:
            raise ValueError(
                f"Module '{name}' not found"
            )

        module.on_enable()

        self._status[name] = "active"

    def disable(
        self,
        name: str,
    ):
        module = module_registry.get(
            name
        )

        if module is None:
            raise ValueError(
                f"Module '{name}' not found"
            )

        module.on_disable()

        self._status[name] = "inactive"

    def get(
        self,
        name: str,
    ):
        return module_registry.get(
            name
        )

    def status(
        self,
        name: str,
    ) -> str | None:
        return self._status.get(
            name
        )

    def list_installed(
        self,
    ):
        result = []

        for module in module_registry.list():
            result.append(
                {
                    "name": module.name,
                    "version": module.version,
                    "description": module.description,
                    "status": self._status.get(
                        module.name,
                        "installed",
                    ),
                }
            )

        return result


module_manager = ModuleManager()
