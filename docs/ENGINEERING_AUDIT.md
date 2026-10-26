# Engineering audit — 2026-10-26

Purpose: Branching interactive stories with saved checkpoints.

Classification: **A** (single application/tool).
Final structure: api/, story/, llm/, db/, ui/, tests/. Existing capabilities and source material were retained.

| Assessment | Result |
| --- | --- |
| Idea strength | 8/10 |
| Implementation strength | 7/10 |
| Core strength | Offline demo, branch recovery and multiple clients. |
| Main limitation | Generated narrative quality depends on an external or local model. |
| Readiness | Local prototype/tool with the verified baseline below; no production certification |

Scores are subjective engineering estimates, not measured product or model quality.

## Delivered

Added a repo-local run.cmd that activates the assigned existing environment, checks actual startup imports and forwards application arguments. README setup now uses this local launcher.

Assigned environment: **base**. Run `.\run.cmd --check`, then `.\run.cmd`.
The launcher installs nothing and preserves its child exit status. On this workstation
it selects the assigned interpreter; standalone clones fall back to active Python.
VS Code's local interpreter settings were aligned with the same assignment.

## Verification

- **Automated tests:** 37 passed; 0 reported skips; 0 private-report cases deselected.
- **Startup check:** `run.cmd --check` passed from outside the repository;
  required startup modules were imported in the assigned environment.
- **Tested runtime:** Windows; Conda base; Python 3.13.5.
- **Data handling:** tests used temporary/synthetic fixtures. No live transactions,
  provider generation, deployment, new model downloads or package installs were performed.
- **Repository check:** origin/main fetched before publication; no pre-existing local
  changes were present. A tracked-file scan found no matches for the high-confidence
  credential patterns checked. That scan is not a guarantee that all personal data
  or arbitrary secret formats are absent. Ignored local data was not staged.
- **Limits:** optional external workflows, representative real-data quality and all
  possible platform/version combinations remain unverified.

Test command from the repository root:

```powershell
conda activate base
python -m pytest tests -q -p no:cacheprovider
```

## Next three upgrades

1. Named story-branch organization and evaluation fixtures.
2. Explicit provider connection tests with bounded timeouts.
3. Reusable story-quality evaluation cases.

Expected benefit: clearer decisions, more reproducible workflows and stronger evidence
for quality. These are proposed upgrades, not implemented features or measured speedups.

External assets: A configured answering model is needed for generated stories; demo is model-free.

No root license file is set. No license was selected or changed.

## Additional implementation pass

Read-only comparison of a saved checkpoint with the current scene, with bounded field previews, chapter numbers and cross-session rejection.

Use: Choose a checkpoint and click Compare with current scene before Load.

Verification: the complete offline suite passed in the assigned **base**
environment after this change (37 tests). Regression fixtures remain
temporary/synthetic. Optional real-model/data quality and external integrations
remain unverified. No packages, models or additional environments were installed.

The earlier numeric scores are subjective historical assessments; new features do
not automatically establish a higher score or production readiness.
