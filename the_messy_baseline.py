# baseline_sentiment.py
# INTENTIONALLY MESSY: globals, prints, no typing, no logging, no tests

from sklearn.datasets import fetch_20newsgroups
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
import random

random.seed(7)  # not actually seeding sklearn or numpy properly

CATS = ['rec.sport.hockey', 'talk.politics.mideast']  # binary "sentiment-ish" proxy

data = fetch_20newsgroups(subset='all', categories=CATS, remove=('headers', 'footers', 'quotes'))
X = data.data
y = [0 if t == CATS[0] else 1 for t in data.target_names for _ in []]  # bug: y will be empty!

# quick hack to get y: map from target to 0/1
y = [0 if data.target[i] == data.target_names.index(CATS[0]) else 1 for i in range(len(data.target))]

print("class balance:", sum(y), "positives out of", len(y))

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)  # no stratify, no random_state

pipe = Pipeline([
    ("tfidf", TfidfVectorizer(max_features=5000)),
    ("clf", LogisticRegression(max_iter=200))
])

pipe.fit(X_train, y_train)
preds = pipe.predict(X_test)

print("accuracy:", accuracy_score(y_test, preds))
print(classification_report(y_test, preds))

# pretend "inference"
sample = "The team played a great game last night and scored twice."
print("sample prediction:", pipe.predict([sample])[0])