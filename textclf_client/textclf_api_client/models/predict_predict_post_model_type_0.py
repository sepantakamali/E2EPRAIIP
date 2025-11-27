from enum import Enum


class PredictPredictPostModelType0(str, Enum):
    LATEST = "latest"
    STABLE = "stable"

    def __str__(self) -> str:
        return str(self.value)
