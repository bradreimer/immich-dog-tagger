# DT-0933 Validation Report

## Summary

The real review -> correction -> learning -> reclassification loop was exercised against production-backed review items.

A real unknown classification was corrected via CLI, persisted as a review action, created a review-sourced embedding example, and then influenced subsequent reclassification.

## Commands and Outcomes

1. Select a real pending review candidate and identities from production state:

```bash
sqlite3 data/breimer/state/state.db "select id,name from identities order by id;"
sqlite3 data/breimer/state/state.db "select cc.id,cc.identity,cc.confidence,a.immich_asset_id from crop_classifications cc join crops c on c.id=cc.crop_id join detections d on d.id=c.detection_id join assets a on a.id=d.asset_id where not exists (select 1 from review_actions ra where ra.classification_id=cc.id) order by cc.confidence asc limit 10;"
```

2. Apply real correction and trigger learning path:

```bash
uv run immich-dog-tagger review-apply 14 Cooper
```

Outcome:
- `Applied review: 14 -> Cooper`

3. Reclassify all crops after correction:

```bash
uv run immich-dog-tagger classify --all
```

Outcome:
- `Classified: 221`
- Identity outputs included `Cooper: 2` after reclassification.

4. Verify persistence and learning artifacts:

```bash
sqlite3 data/breimer/state/state.db "select id,classification_id,action,identity,original_identity,created_at from review_actions where classification_id=14 order by id desc limit 1;"
sqlite3 data/breimer/state/state.db "select count(*) from embedding_examples where source='REVIEW';"
```

Outcome:
- Review action persisted: `CORRECT` for classification `14` with identity `Cooper`.
- Review-sourced examples count increased to `26`.

## Observations

- Correction persistence: confirmed.
- Learning example creation from correction: confirmed.
- Reclassification run completed successfully post-correction.
- Review history remained present after subsequent independent CLI process execution.
- Mission Control/state remains authoritative via `state.db` evidence.

## Note on review-reason coverage

This production snapshot is heavily unknown-biased and does not naturally contain candidate-conflict rows. Unknown and correction paths were validated directly in production, and low-confidence/candidate-conflict paths remain covered by existing automated test suites.
