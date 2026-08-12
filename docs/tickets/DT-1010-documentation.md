# DT-1010: v1.0 user and operator documentation

## **ID**

DT-1010

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-10

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Make the product understandable without ML expertise.

## **Context**

DT-1001 through DT-1009 deliver the review -> reclassify loop, its safety guarantees, and its metrics, but a new user still needs a written path from an empty project to progressively improved automatic classification -- what to do first, when to click Reclassify, and what the confidence states mean.

## **Implementation notes**

- Added [docs/workflow.md](../workflow.md) ("New Project Workflow"), covering all seven required points: first-project setup, the 50-100 review batch framed explicitly as a starting point rather than a threshold the system checks for, when to click Reclassify and why it's safe to run repeatedly, a table defining confident/needs-review/unknown against the actual centralized policy semantics, the iterative review -> reclassify loop as a diagram, backups/state/recovery (the real `backup`/`validate-backup`/`restore`/`check-derived-data` CLI commands and the diagnostics panel), and known v1.0.0 limitations (no temporal weighting, no separate training step, no calibrated probabilities, single active operation at a time) with a link to the spec's full non-goals list.
- Linked from `README.md`'s Quick Start section so it's discoverable at the point a new user finishes their first pipeline run.
- Written and cross-checked against the actual DT-1001-1009 implementation (policy thresholds, CLI command names, diagnostics fields) rather than the spec's aspirational description, so it reflects what v1.0.0 actually does.

## **Acceptance criteria**

A new user can follow the workflow from an empty project to progressively improved automatic classification using only the documentation.

## **Testing requirements**

Documentation-only ticket; reviewed for accuracy against the actual DT-1001-1009 implementation. `./scripts/check.sh` passes (no code changed).

## **Dependencies**

DT-1001 through DT-1009 (documents the finished feature set).

## **Suggested commit message**

`docs(DT-1010): add v1.0 user and operator documentation`
