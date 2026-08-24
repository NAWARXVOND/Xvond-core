from backend.app.core.module import BaseModule


class ModuleRegistry:

    def __init__(self):
        self._modules: dict[str, BaseModule] = {}

    def register(
        self,
        module: BaseModule,
    ):
        if not module.name:
            raise ValueError(
                "Module must have a name"
            )

        self._modules[module.name] = module

    def get(
        self,
        name: str,
    ) -> BaseModule | None:
        return self._modules.get(name)

    def exists(
        self,
        name: str,
    ) -> bool:
        return name in self._modules

    def list(
        self,
    ) -> list[BaseModule]:
        return list(
            self._modules.values()
        )


module_registry = ModuleRegistry()
