from .data import load_split
from .model import build_pipeline, train, predict
from .evaluate import evaluate
from .persistence import save_model, load_model

__all__ = [
    "load_split",
    "build_pipeline",
    "train",
    "predict",
    "evaluate",
    "save_model",
    "load_model",
    ]

__version__ = "0.1.0"