# Benchmark evidence

Verified September 7, 2026. All four methods are measured for each of four tasks. Scores below describe bounded historical samples, not expected production performance.

| Task | Method | n | Accuracy | Chance | Majority | Exact train/test overlap |
|---|---|---:|---:|---:|---:|---:|
| comment-spam-detection | Keyword Rules | 100 | 69.00% | 50.00% | 52.00% | 0.0% |
| comment-spam-detection | TF-IDF + Logistic Regression | 100 | 100.00% | 50.00% | 52.00% | 0.0% |
| comment-spam-detection | Small hosted · GPT OSS 20B | 100 | 95.00% | 50.00% | 52.00% | 0.0% |
| comment-spam-detection | Large hosted · GPT OSS 120B | 100 | 94.00% | 50.00% | 52.00% | 0.0% |
| sentiment-classification | Keyword Rules | 120 | 57.50% | 50.00% | 51.67% | 0.0% |
| sentiment-classification | TF-IDF + Logistic Regression | 120 | 86.67% | 50.00% | 51.67% | 0.0% |
| sentiment-classification | Small hosted · GPT OSS 20B | 120 | 96.67% | 50.00% | 51.67% | 0.0% |
| sentiment-classification | Large hosted · GPT OSS 120B | 120 | 96.67% | 50.00% | 51.67% | 0.0% |
| spam-detection | Keyword Rules | 120 | 90.00% | 50.00% | 87.50% | 0.0% |
| spam-detection | TF-IDF + Logistic Regression | 120 | 99.17% | 50.00% | 87.50% | 0.0% |
| spam-detection | Small hosted · GPT OSS 20B | 120 | 86.67% | 50.00% | 87.50% | 0.0% |
| spam-detection | Large hosted · GPT OSS 120B | 120 | 94.17% | 50.00% | 87.50% | 0.0% |
| support-request-routing | Keyword Rules | 120 | 45.00% | 14.29% | 14.17% | 0.0% |
| support-request-routing | TF-IDF + Logistic Regression | 120 | 77.50% | 14.29% | 14.17% | 0.0% |
| support-request-routing | Small hosted · GPT OSS 20B | 120 | 65.83% | 14.29% | 14.17% | 0.0% |
| support-request-routing | Large hosted · GPT OSS 120B | 120 | 67.50% | 14.29% | 14.17% | 0.0% |

## How to interpret the comparison

Methods share evaluation IDs, labels, dataset version, and sampling seed within each task. Accuracy was recalculated from saved predictions; IDs and artifact hashes were checked. The CSV records provenance hashes, run IDs, measured median latency, and explicitly estimated costs. The implementation and raw experiment artifacts remain private; hashes identify records but do not independently reproduce the experiment.

The hosted comparators are GPT OSS 20B and GPT OSS 120B through Groq. The larger comparator is not a claim about the current frontier of AI. Training and setup are excluded from inference latency. Provider prices and runtime-based cost projections are assumptions, not billed invoices, and do not decide recommendations.

The decision rule chooses the lowest-complexity method meeting all requirements after every declared method has been measured. At default requirements, traditional ML is selected for SMS and comment spam; GPT OSS 20B for sentiment; no method passes complaint routing. Completing 4/4 does not mean 4/4 pass.

## Limits and next experiments

No protected-group annotations are available, so demographic fairness is unknown. Class precision/recall and uncertainty appear in the product. Zero normalized-text overlap does not rule out semantic overlap or hosted-model pretraining contamination. Small, historical samples need larger independent holdouts, time/domain splits, repeated runs, and task-specific harm analysis before operational use. A 100% score on 100 examples is not a guarantee.

## Public source material

- [UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms+spam+collection)
- [UCI YouTube Spam Collection](https://archive.ics.uci.edu/dataset/380/youtube+spam+collection) — CC BY 4.0; 1,741 distinct texts after deduplication.
- [Consumer Financial Protection Bureau complaint database](https://www.consumerfinance.gov/data-research/consumer-complaints/)
- [Stanford Sentiment Treebank](https://nlp.stanford.edu/sentiment/)

Dataset terms remain with their respective owners; this showcase does not redistribute source corpora.
