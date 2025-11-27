from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, train, predict

def test_train_and_predict():
    X_train, X_test, y_train, y_test = load_split(DEFAULT.categories, DEFAULT.test_size, DEFAULT.random_state)
    pipe = build_pipeline(DEFAULT.max_features, DEFAULT.max_iter)
    trained = train(pipe, X_train, y_train)
    preds = predict(trained, X_test)
    assert len(preds) == len(y_test)
    assert set(preds).issubset({0, 1})