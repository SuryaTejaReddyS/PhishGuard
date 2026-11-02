# PhishGuard: Real-Time Phishing Detection with Human Override

PhishGuard is an agentic pipeline that automatically scores incoming messages for phishing risk, quarantines the likely phishing ones, and lets a human reviewer confirm or override each decision. It was built for the SIH25159 problem statement: *"Phishing attempts need real-time detection with human override."*

## How it works

Each incoming email passes through a chain of single-purpose agents:

1. **Feature extraction agent** pulls links from the email and converts each URL into 27 numeric features (length, subdomains, IP host, suspicious keywords, entropy, and so on).
2. **Detection agent** runs a trained Random Forest and returns a phishing probability plus human-readable reasons.
3. **Decision agent** compares the score with a threshold (default `0.7`). Scores at or above it are quarantined, and the rest are delivered.
4. **Human reviewer dashboard** shows quarantined emails with their score and reasons. The reviewer clicks **Confirm phishing** (stays blocked) or **Override: release** (goes to the inbox).
5. **Logging** stores every decision, score, processing time, and reviewer action in SQLite for evaluation.

```
Incoming email -> Feature extraction -> Detection (ML score) -> Score >= threshold?
        no  -> Deliver to inbox
        yes -> Quarantine -> Human review -> Confirm (blocked) | Override (released)
                                          -> Log decisions + outcomes
```

## Project structure

```
PhishGuard/
├── app.py                  # Streamlit dashboard (reviewer UI + live simulator)
├── evaluate.py             # Confusion matrix, threshold comparison, human-in-the-loop results
├── data/
│   ├── verified_online.csv # PhishTank verified phishing URLs (label 1)
│   ├── top-1m.csv         # Top-sites list used for safe URLs (label 0)
│   ├── train.csv / val.csv / test.csv
│   ├── *_features.csv      # Extracted feature matrices
│   └── phishguard.db       # SQLite log (created at runtime)
├── models/
│   └── detector.joblib     # Saved best model + feature column order
├── results/                # Generated figures and tables
└── src/
    ├── build_dataset.py    # Builds, balances, and splits the dataset
    ├── features.py         # Feature extraction agent
    ├── train.py            # Trains and compares three models
    ├── detector.py         # Detection agent (score + reasons)
    ├── pipeline.py         # Decision and routing logic
    ├── store.py            # SQLite storage
    ├── stream_demo.py      # Streams emails to measure processing time
    ├── test_features.py    # Quick feature sanity check
    └── test_pipeline.py    # Quick end-to-end check
```

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install pandas scikit-learn streamlit joblib matplotlib seaborn tldextract
```

## Data

| Source | Use | Label |
|---|---|---|
| [PhishTank](https://phishtank.org) `online-valid.csv` | Verified phishing URLs | 1 |
| Top-sites list (`top-1m.csv`) | Legitimate domains, turned into URLs with `https://`, optional `www.`, and common paths | 0 |

Place both files in `data/` (the PhishTank file as `verified_online.csv`). PhishTank does not require an API key for a single download of the CSV, but it limits downloads per day, so keep a local copy.

## Usage

Run these from the project root, in order:

```bash
python src/build_dataset.py     # 10,000 phishing + 10,000 safe, split 70/15/15
python src/features.py          # writes data/*_features.csv
python src/train.py             # compares models, saves models/detector.joblib
python src/test_pipeline.py     # optional end-to-end check
streamlit run app.py            # opens the dashboard at localhost:8501
python evaluate.py              # confusion matrices and threshold analysis
```

### Using the dashboard

- **Send 1 / Send 10 emails** pushes random test emails through the pipeline.
- **Send your own email** lets you type a message containing a link and see how it is scored.
- **Quarantine queue** lists flagged emails with their reasons and the Confirm and Override buttons.
- **Full log** shows every decision, the true label, and the processing time.
- **Auto-stream** (sidebar) sends a new email every 2 seconds to demonstrate real-time behaviour. Turn it off before clicking review buttons.

## Results

### Model comparison (validation set)

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Logistic Regression | 0.866 | 0.915 | 0.807 | 0.857 |
| **Random Forest** | **0.977** | 0.992 | 0.961 | **0.976** |
| Gradient Boosting | 0.969 | 0.994 | 0.944 | 0.968 |

Removing the path and query features (ablation) lowers Random Forest accuracy only from 0.977 to 0.965, so the model does not depend on the synthetic safe-URL paths.

### Confusion matrix on the held-out test set (3,000 emails, threshold 0.7)

| | Delivered | Quarantined |
|---|---|---|
| **Safe** | 1,492 | 8 |
| **Phishing** | 81 | 1,419 |

Accuracy 97.0%, precision 99.4%, recall 94.6%, F1 0.970. Figures are saved in `results/`.

### Threshold trade-off

| Threshold | False positives | False negatives | Precision | Recall | F1 |
|---|---|---|---|---|---|
| 0.3 | 50 | 41 | 0.967 | 0.973 | 0.970 |
| 0.5 | 22 | 56 | 0.985 | 0.963 | 0.974 |
| 0.7 | 8 | 81 | 0.994 | 0.946 | 0.970 |
| 0.9 | 0 | 134 | 1.000 | 0.911 | 0.953 |

Lower thresholds catch more phishing but send more safe mail to the reviewer. Higher thresholds do the reverse.

### Human override

With a simulated reviewer who is correct 95% of the time, false positives drop from 8 to 1. False negatives rise from 81 to 158 because the reviewer sometimes releases real phishing. The 95% accuracy is an assumption, not a measured value.

## Limitations

- **URL-only scoring.** The pipeline scores links, not the email text, sender, or headers. Short, clean-looking phishing domains are often missed.
- **Synthetic safe URLs.** Safe URLs are real domains with generated paths, so some features (for example `/cart` paths and `subdomain_length`) partly reflect how the data was built. Several false positives are `/cart` pages for this reason.
- **Email wording is templated.** The dashboard wraps URLs in neutral templates, so the email text carries no signal.
- **Human review only covers quarantined mail.** A phishing email scored below the threshold is delivered and never reviewed.
- **Small shortener list.** Services such as `bitly.cx`, `did.li`, and `ur0.jp` are not recognised.

## Future work

- Add a **medium-risk band** (for example scores 0.4 to 0.7) that is also sent to the reviewer.
- Add **email text and header features** such as urgency wording and sender/link domain mismatch.
- Expand the **URL shortener list** and add domain-age or reputation lookups.
- Use reviewer decisions as **feedback labels** to retrain the model.
- Optionally add an LLM agent to explain flagged emails in plain language.

## Data and ethics note

PhishTank data is community-submitted and may contain mistakes. Phishing URLs in the dataset should never be opened in a browser. The project only analyses URL strings and never visits them.