from abc import ABC


class BaseModule(ABC):
    name: str = ""
    version: str = "1.0.0"
    description: str = ""

    def info(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
        }

    def on_enable(self):
        pass

    def on_disable(self):
        pass
