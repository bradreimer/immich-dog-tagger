# Roadmap

## v0.4.0 - Human Review Foundation

Goal:
Create a reliable human review workflow.

Completed:
- Review API
- Review queue
- Browser UI
- Correct action
- Skip action
- Review history tracking

Exit criteria:
Completed.

---

## v0.5.0 - Review Workflow Stabilization

Goal:
Make human review and active learning observable and dependable.

Features:
- Learning statistics
- Review progress visibility
- Review workflow improvements
- Better embedding example management
- Documentation of workflow

Exit criteria:
- Review actions are measurable
- Learning progress is visible
- Workflow documented

---

## v0.9.4 - Dynamic Dog Management

Goal:
Remove hard-coded dog names and let operators manage dog identities from Mission Control.

Completed:
- persistent dog identity model
- dog management API
- Mission Control dog management UI
- regression coverage for empty-install behavior

Exit criteria:
Completed.

---

## v1.0.0 - Review-Driven Learning Loop

See [docs/specs/v1.0.0.md](specs/v1.0.0.md) for the full specification and [docs/workflow.md](workflow.md) for the operator-facing workflow guide.

Goal:
Let a user with a new project and no labeled examples progressively reduce manual review through a review -> reclassify loop, without needing to understand embeddings or model internals.

Completed:
- Centralized nearest-neighbor classifier policy (DT-1004)
- Reclassification service/job that reuses stored embeddings and reviewed examples without touching reviewed ground truth (DT-1001)
- Review-to-example ground-truth hardening, closing a real leakage defect (DT-1003)
- Job lifecycle/idempotency/recovery for Reclassify (DT-1005)
- Reclassify action on Mission Control and a Learning Progress dashboard (DT-1002, DT-1006; the dashboard moved to its own Metrics tab in v1.1's DT-1103)
- Pipeline/correction lifecycle logging (DT-1007)
- Scale validation: two N+1 defects found and fixed (DT-1008)
- End-to-end review-driven learning loop regression tests (DT-1009)
- v1.0 user and operator documentation (DT-1010)

Remaining:
- DT-1011 release validation against the full v1.0.0 acceptance criteria, then tag v1.0.0.

## Future Milestones

## v1.1 - Automation Coverage Dashboard

See [docs/specs/v1.1-automation-coverage-dashboard.md](specs/v1.1-automation-coverage-dashboard.md).

Goal:
Answer "is the system getting better at doing the work I used to have to do manually?" with a dedicated Metrics tab, complete per-pass trend data, and one prominent automation-rate number.

Completed:
- DT-1103: dedicated Metrics tab, next to Mission Control
- DT-1101: snapshot labeled-example count and review-queue size per classification pass
- DT-1102: reconcile the review-queue metric definition and add a prominent automation-rate metric

Exit criteria:
Completed.

## v1.2 - Visual Style Refresh

See [docs/specs/v1.2-visual-style-refresh.md](specs/v1.2-visual-style-refresh.md).

Goal:
Give the app one consistent visual identity -- a sidebar navigation shell, a single blue action
accent, consistent status colors, and a stat-tile/chart pattern -- across all four existing tabs,
replacing the horizontal pill nav and per-page ad-hoc styling.

Completed:
- DT-1104: blue accent design tokens, validated status/categorical color palette, sidebar
  navigation shell, reusable stat-tile primitive
- DT-1105: rolled the style out to Mission Control, Metrics (including new donut and trend
  charts built from existing `GET /metrics` data), Job Queue, and Review's surrounding chrome

Exit criteria:
Completed.

## Active Learning Improvements

Goal:
Increase classification quality through better feedback loops.

Potential areas:
- improved reference-example selection
- reference-set curation workflows
- confidence analysis

## Productization

Goal:
Make the tool easier to operate.

Potential areas:
- polished CLI
- complete web workflow
- automated synchronization
