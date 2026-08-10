# DT-0931 Validation Report

## Summary

A bounded, reproducible representative dataset was selected from the real Immich library on schnorbit and recorded in:

- `docs/validation/v0.9.3/dt-0931-representative-dataset.csv`

The manifest is generated from authoritative `state.db` records and includes cohorts for known identity, unknown identity, reviewed items, multi-detection assets, missing-captured-at metadata, and recently scanned assets.

## Commands

```bash
sqlite3 -header -csv data/breimer/state/state.db "with base as (select a.id as asset_pk, a.immich_asset_id, a.captured_at, a.created_at, a.status, count(distinct d.id) as detection_count, min(cc.confidence) as min_confidence, max(case when cc.identity is null then 1 else 0 end) as has_unknown, max(case when ra.id is not null then 1 else 0 end) as has_review_action from assets a left join detections d on d.asset_id=a.id left join crops c on c.detection_id=d.id left join crop_classifications cc on cc.crop_id=c.id left join review_actions ra on ra.classification_id=cc.id group by a.id), known as (select 'known_identity' as cohort,* from base where has_unknown=0 and min_confidence is not null order by created_at asc limit 12), unknowns as (select 'unknown_identity' as cohort,* from base where has_unknown=1 order by created_at asc limit 12), reviewed as (select 'reviewed' as cohort,* from base where has_review_action=1 order by created_at asc limit 12), multi as (select 'multi_detection' as cohort,* from base where detection_count >= 2 order by detection_count desc, created_at asc limit 12), no_capture as (select 'missing_captured_at' as cohort,* from base where captured_at is null order by created_at asc limit 12), fresh as (select 'recently_scanned' as cohort,* from base order by created_at desc limit 12) select cohort, asset_pk, immich_asset_id, status, created_at, captured_at, detection_count, min_confidence, has_unknown, has_review_action from (select * from known union all select * from unknowns union all select * from reviewed union all select * from multi union all select * from no_capture union all select * from fresh) order by cohort, created_at;" > docs/validation/v0.9.3/dt-0931-representative-dataset.csv
```

## Observations

- Immich connectivity validation: `Found 1000 assets`.
- Representative manifest generated from real state linked to Immich asset IDs.
- Temporal metadata includes assets with `captured_at` present and missing.
- Existing processed assets and review-touched assets are included.
- No source Immich assets were altered or deleted.

## Baseline Counts

```text
assets: 1000
detections: 3378
crops: 221
crop_classifications: 221
review_actions: 26
embedding_examples: 61
```
