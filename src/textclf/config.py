from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class Config:
    categories: List[str]
    test_size: float
    random_state: int
    shuffle: bool
    max_features: int
    max_iter: int

# DEFAULT = Config(
#     categories=['rec.sport.hockey', 'talk.politics.mideast'],
#     test_size=0.2,
#     random_state=42,
#     max_features=5000,
#     max_iter=200
# )

DEFAULT = Config(
    categories=['rec.sport.hockey', 'talk.politics.mideast'],
    test_size=0.2,
    random_state=42,
    shuffle=True,
    max_features=5000,
    max_iter=200
)

[
  {
    "token_id": "ui-local",
    "subject": "ui-service",
    "client_id": "ui-service",
    "scopes": ["predict:run", "models:read", "version:read", "whoami:read"],
    "active": true,
    "token_hash": "a7bdfd212b8604b8ccce6a815a19abed656aa3b708788e0521e4fa3bda1c74c8",
    "issued_at": "2026-04-23T00:00:00Z",
    "expires_at": "2026-12-31T23:59:59Z",
    "revoked_at": null
  }
]