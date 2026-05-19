from typing import List, Tuple
from sklearn.datasets import fetch_20newsgroups
from sklearn.model_selection import train_test_split

def load_split(categories: List[str], test_size: float, random_state: int, shuffle: bool
               ) -> Tuple[list[str], List[str], List[int], List[int]]:
    data = fetch_20newsgroups(subset='all', categories=categories, shuffle=shuffle, remove=('headers', 'footers', 'quotes'), random_state=random_state)
    X: List[str] = data.data
    # map original targets to {0,1} using requested categories order
    label0 = data.target_names.index(categories[0])
    label1 = data.target_names.index(categories[1])
    y: List[int] = [0 if t == label0 else 1 for t in data.target]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, shuffle=shuffle, stratify=y
    )
    return X_train, X_test, y_train, y_test