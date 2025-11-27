from textclf.data import load_split
from textclf.config import DEFAULT

def test_load_split_shapes():
    X_train, X_test, y_train, y_test = load_split(DEFAULT.categories, DEFAULT.test_size, DEFAULT.random_state)
    assert len(X_train) > 0 and len(X_test) > 0
    assert len(X_train) == len(y_train)
    assert len(X_test) == len(y_test)
    # class labels must be 0/1 only
    assert set(y_train).issubset({0, 1})
    assert set(y_test).issubset({0, 1})