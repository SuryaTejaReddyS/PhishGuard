import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score)

sys.path.insert(0, str(Path(__file__).parent / "src"))
from features import build_matrix

Path("results").mkdir(exist_ok=True)

# ---- score the whole test set once ----
bundle = joblib.load("models/detector.joblib")
model, cols = bundle["model"], bundle["columns"]
test = pd.read_csv("data/test.csv")
X, y = build_matrix(test)
prob = model.predict_proba(X[cols])[:, 1]


def metrics_at(th):
    pred = (prob >= th).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return pred, dict(threshold=th, TP=tp, FP=fp, TN=tn, FN=fn,
                      accuracy=accuracy_score(y, pred),
                      precision=precision_score(y, pred),
                      recall=recall_score(y, pred),
                      f1=f1_score(y, pred))


# ---- 1. confusion matrix at the pipeline threshold ----
TH = 0.7
pred, m = metrics_at(TH)
cm = confusion_matrix(y, pred)
plt.figure(figsize=(5, 4))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=["Delivered", "Quarantined"],
            yticklabels=["Safe", "Phishing"])
plt.xlabel("System decision")
plt.ylabel("Actual")
plt.title(f"Confusion matrix (threshold {TH})")
plt.tight_layout()
plt.savefig("results/confusion_matrix.png", dpi=200)
print(f"=== Confusion matrix at threshold {TH} ===")
print(cm)
print({k: round(float(v), 4) for k, v in m.items()})

# ---- 2. threshold comparison ----
rows = [metrics_at(t)[1] for t in [0.3, 0.5, 0.7, 0.9]]
th_table = pd.DataFrame(rows).round(4)
th_table.to_csv("results/threshold_comparison.csv", index=False)
print("\n=== Threshold comparison ===")
print(th_table.to_string(index=False))

# ---- 3. human-in-the-loop effect ----
# Reviewer only sees quarantined emails. Assume they judge correctly with
# probability REVIEWER_ACC (1.0 = perfect reviewer).
REVIEWER_ACC = 0.95
rng = np.random.default_rng(42)
quarantined = pred == 1
reviewer_correct = rng.random(len(y)) < REVIEWER_ACC
# reviewer releases an email if they think it's safe
reviewer_says_safe = np.where(reviewer_correct, y == 0, y == 1)
final_blocked = quarantined & ~reviewer_says_safe
final_pred = final_blocked.astype(int)

tn, fp, fn, tp = confusion_matrix(y, final_pred).ravel()
fp_before = int(((pred == 1) & (y == 0)).sum())
rescued = int(((pred == 1) & (y == 0) & ~final_blocked).sum())
print(f"\n=== With human reviewer (accuracy {REVIEWER_ACC:.0%}) ===")
print(f"Safe emails wrongly quarantined by the AI: {fp_before}")
print(f"  of which rescued by human override:      {rescued}")
print(f"Final false positives: {fp}   Final false negatives: {fn}")
print(f"Final precision: {precision_score(y, final_pred):.4f}   "
      f"Final recall: {recall_score(y, final_pred):.4f}")

plt.figure(figsize=(5, 4))
sns.heatmap(confusion_matrix(y, final_pred), annot=True, fmt="d", cmap="Greens",
            xticklabels=["Delivered", "Blocked"], yticklabels=["Safe", "Phishing"])
plt.xlabel("Final outcome (after human review)")
plt.ylabel("Actual")
plt.title("Confusion matrix with human override")
plt.tight_layout()
plt.savefig("results/confusion_matrix_with_human.png", dpi=200)

# ---- 4. the emails the AI got wrong ----
errs = test.assign(score=prob.round(3))[(pred != y)]
errs.to_csv("results/misclassified.csv", index=False)
print(f"\nSaved {len(errs)} misclassified rows to results/misclassified.csv")