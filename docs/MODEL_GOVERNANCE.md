# Model Governance

1. The target is currently a sandbox proxy and must be formally reviewed before operational use.
2. Training uses chronological holdout, not random future-to-past mixing.
3. Training is blocked below configured minimum sample/class counts.
4. Every model version has metadata, metrics, feature schema and global importance.
5. Only one registered model is active at a time; activation is explicit.
6. Model probability is not a regulatory decision. Policy output requires human review.
7. Data-quality FAIL prevents model-based decisions.
8. Synthetic Sandbox data is stored separately and must not be merged into real training data.
9. Retraining should be triggered after meaningful new history, KPI definition changes, source methodology changes or material performance drift.
