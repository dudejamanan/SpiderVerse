"""
Phase 4 baseline: shared TF-IDF matrix -> 4 independent logistic regressions.

This is the performance floor and the fallback path. It trains in seconds, so run
it every time you regenerate data — if the transformer can't beat this, something
is wrong with the transformer, not with the task.

Usage:
    python baseline_sklearn.py --data data/ --out artifacts/
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score

HEADS = ["zone_id", "parameter", "direction", "intensity"]


def load_split(data_dir, name):
    df = pd.read_csv(os.path.join(data_dir, f"{name}.csv"))
    if "keep" in df.columns:
        df = df[df["keep"] == 1]
    return df.reset_index(drop=True)


def joint_exact_match(y_true: dict, y_pred: dict) -> float:
    """Fraction of rows where ALL FOUR heads are correct. The number that
    actually predicts whether the user gets a correct reply."""
    n = len(next(iter(y_true.values())))
    ok = np.ones(n, dtype=bool)
    for h in HEADS:
        ok &= np.asarray(y_true[h]) == np.asarray(y_pred[h])
    return float(ok.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="artifacts")
    ap.add_argument("--test", action="store_true",
                    help="evaluate on test.csv instead of val.csv (Phase 5 only, once)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    train = load_split(args.data, "train")
    eval_name = "test" if args.test else "val"
    evl = load_split(args.data, eval_name)
    print(f"train {len(train)} rows / {eval_name} {len(evl)} rows\n")

    # Stopwords and stemming are fine HERE (dense vocab helps linear models) but
    # must NOT be applied to the transformer — "not"/"too"/"very" carry the labels.
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True,
                          lowercase=True, min_df=1)
    X_tr = vec.fit_transform(train["text"])
    X_ev = vec.transform(evl["text"])
    print(f"TF-IDF vocab: {len(vec.vocabulary_)} features\n")

    models, y_true, y_pred, summary = {}, {}, {}, {}
    for h in HEADS:
        clf = LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0)
        clf.fit(X_tr, train[h])
        models[h] = clf
        y_true[h] = evl[h].to_numpy()
        y_pred[h] = clf.predict(X_ev)
        macro_f1 = f1_score(y_true[h], y_pred[h], average="macro", zero_division=0)
        summary[h] = round(macro_f1, 4)
        print(f"=== {h}  (macro F1 {macro_f1:.3f}) ===")
        print(classification_report(y_true[h], y_pred[h], zero_division=0, digits=3))

    jem = joint_exact_match(y_true, y_pred)
    summary["joint_exact_match"] = round(jem, 4)
    print(f"JOINT EXACT MATCH ({eval_name}): {jem:.3f}\n")

    # parameter confusion matrix: temperature/humidity/airflow mixups are the
    # failure mode most likely to send a wrong command to the actual HVAC unit.
    labels = sorted(set(y_true["parameter"]) | set(y_pred["parameter"]))
    cm = confusion_matrix(y_true["parameter"], y_pred["parameter"], labels=labels)
    print("parameter confusion (rows=true, cols=pred)")
    print(pd.DataFrame(cm, index=labels, columns=labels).to_string(), "\n")

    joblib.dump({"vectorizer": vec, "models": models, "heads": HEADS},
                os.path.join(args.out, "baseline.joblib"))
    with open(os.path.join(args.out, f"baseline_metrics_{eval_name}.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"saved -> {args.out}/baseline.joblib")


if __name__ == "__main__":
    main()
