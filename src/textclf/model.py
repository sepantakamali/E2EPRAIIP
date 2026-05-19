from typing import List
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.feature_selection import SelectKBest, chi2

def build_pipeline(max_features: int, max_iter: int) -> Pipeline:
    # return Pipeline([
    #     ("tfidf", TfidfVectorizer(max_features=max_features)),
    #     ("clf", LogisticRegression(max_iter=max_iter))
    # ])
    return Pipeline([
    ('vectorizer', TfidfVectorizer(stop_words='english', max_features=50000)),
    ('feature_selection', SelectKBest(chi2, k=5000)), # Reduce to top 5000 features
    ('classification', LogisticRegression(solver='saga', multi_class='multinomial', max_iter=max_iter))
])

def train(pipe: Pipeline, X_train: List[str], y_train: List[int]) -> Pipeline:
    pipe.fit(X_train, y_train)
    return pipe

def predict(pipe: Pipeline, texts: List[str]) -> List[int]:
    # sklearn returns ndarray; turn into List[int]
    return pipe.predict(texts).tolist() # type: ignore[no-any-return]