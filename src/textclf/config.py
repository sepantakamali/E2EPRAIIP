from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class Config:
    categories: List[str]
    test_size: float
    random_state: int
    max_features: int
    max_iter: int

DEFAULT = Config(
    categories=['rec.sport.hockey', 'talk.politics.mideast'],
    test_size=0.2,
    random_state=42,
    max_features=5000,
    max_iter=200
)