from backend.app.core.module import BaseModule


class TestModule(BaseModule):
    name = "test"
    version = "1.0.0"
    description = "Xvond development test module"

    def on_enable(self):
        print("Test module enabled")

    def on_disable(self):
        print("Test module disabled")
