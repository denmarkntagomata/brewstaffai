"""
train_model.py — trains the BrewStaffAI congestion classifier (Objective 2)
Algorithm: Decision Tree (scikit-learn). Easy to explain: it learns IF-THEN rules
such as "IF barista_load > 0.93 THEN Overloaded".

Run:  python train_model.py
Out:  model/model.joblib, model/metrics.json, model/tree_rules.txt
"""
import json
import os

import joblib
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

from labels import FEATURES, CLASSES


def main():
    df = pd.read_csv("data/dataset.csv")
    X, y = df[FEATURES], df["label"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Baseline: always guess the most common label (to show the model is better than guessing)
    base = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr)
    base_acc = accuracy_score(y_te, base.predict(X_te))

    # Tune tree size with 5-fold cross-validation
    grid = GridSearchCV(DecisionTreeClassifier(random_state=42),
                        {"max_depth": [3, 4, 5, 6, 8, 10], "min_samples_leaf": [1, 5, 10, 20]},
                        cv=5, scoring="accuracy")
    grid.fit(X_tr, y_tr)
    model = grid.best_estimator_
    pred = model.predict(X_te)
    acc = accuracy_score(y_te, pred)

    os.makedirs("model", exist_ok=True)
    joblib.dump(model, "model/model.joblib")
    metrics = {
        "test_accuracy": round(acc, 4),
        "baseline_accuracy": round(base_acc, 4),
        "best_params": grid.best_params_,
        "train_rows": len(X_tr), "test_rows": len(X_te),
        "label_counts": df["label"].value_counts().to_dict(),
        "confusion_matrix": {"labels": CLASSES,
                             "matrix": confusion_matrix(y_te, pred, labels=CLASSES).tolist()},
        "report": classification_report(y_te, pred, labels=CLASSES, output_dict=True),
        "feature_importance": dict(sorted(zip(FEATURES, model.feature_importances_.round(4).tolist()),
                                          key=lambda kv: -kv[1])),
    }
    with open("model/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    with open("model/tree_rules.txt", "w") as f:
        f.write(export_text(model, feature_names=FEATURES))

    print(f"Label counts: {metrics['label_counts']}")
    print(f"Best settings: {grid.best_params_}")
    print(f"Baseline accuracy (always guess most common): {base_acc:.1%}")
    print(f"Decision Tree TEST accuracy: {acc:.1%}  (target >= 85%)")
    print(classification_report(y_te, pred, labels=CLASSES))
    print("Confusion matrix (rows = actual, cols = predicted):", CLASSES)
    print(confusion_matrix(y_te, pred, labels=CLASSES))


if __name__ == "__main__":
    main()
