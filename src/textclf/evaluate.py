from typing import Dict, Any, List
from sklearn.metrics import accuracy_score, classification_report

def evaluate(y_true: List[int], y_pred: List[int]) -> Dict[str, Any]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "report": classification_report(y_true, y_pred, digits=3)
    }
