from enum import Enum


class ModelStatePointer(str, Enum):
    CUSTOM = "custom"
    LATEST = "latest"
    STABLE = "stable"

    def __str__(self) -> str:
        return str(self.value)
