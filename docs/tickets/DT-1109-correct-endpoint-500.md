# DT-1109: Fix 500 error on POST /classifications/{id}/correct

## **ID**

DT-1109

## **Related spec**

None -- bug fix, not new behavior.

## **Priority**

High

## **Status**

Completed

## **Goal**

Fix a 500 Internal Server Error on the classification-correct endpoint, which is the API call
behind every "Confirm"/identity-correction action in the Review UI -- a core, frequently-used
workflow.

## **Context**

Reported error (production, via a real "Correct" click in Review):

```
POST /classifications/2/correct HTTP/1.1" 500 Internal Server Error
...
File ".../fastapi/encoders.py", line 337, in jsonable_encoder
    return ENCODERS_BY_TYPE[type(obj)](obj)
  File ".../fastapi/encoders.py", line 85, in <lambda>
    bytes: lambda o: o.decode(),
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc5 in position 2: invalid continuation byte
```

Root cause: `routes/classifications.py`'s `correct` route had no `response_model` and returned
`ClassificationCorrectionService.correct()`'s result -- the raw `CropClassification` ORM object --
directly. FastAPI's default `jsonable_encoder` walks every attribute on an unrecognized object,
including `CropClassification.embedding` (a `LargeBinary` column holding the raw OpenCLIP
embedding vector as bytes), and its built-in `bytes` encoder assumes UTF-8 and calls `.decode()`
unconditionally -- which fails for essentially any real embedding, since embedding bytes are not
text. This was silent in existing tests because none of them populated `embedding` on the test
fixture (defaults to `None`, which never reaches the broken code path).

Every other route in `api/routes/` already pairs a `response_model=` with an explicit
`SomeResponse(...)` construction from the returned domain object (`dogs.py`, `jobs.py`,
`schedules.py`, `review.py`'s list/stats routes); `review.py`'s `skip` route returns a plain
status dict. `classifications.py`'s `correct` route was the only one that skipped both and let a
raw ORM object reach the encoder. Verified by inspecting every route file that none of the others
have this gap.

## **Implementation notes**

- `api/routes/classifications.py`: added `response_model=ClassificationResponse` (an existing,
  previously-unused schema in `api/schemas.py` with exactly the right shape:
  `classification_id`, `crop_id`, `identity`, `confidence`, `filename`) and now builds it
  explicitly from the `CropClassification` the service returns, instead of returning that object
  directly. `filename` is `Path(classification.crop.path).name`.
  `ClassificationCorrectionService.correct()` itself is unchanged -- it still returns the full
  ORM object, which `tests/test_correction.py` and the CLI (`cli.py`) both rely on; the fix is at
  the API boundary, where response shape is actually FastAPI's concern.

## **Acceptance criteria**

- `POST /classifications/{id}/correct` returns 200 with a JSON body (not a 500), including when
  the classification has a populated (non-UTF-8) `embedding` blob.
- Response body matches `ClassificationResponse`'s fields.
- No other route has the same "raw ORM object with a `LargeBinary` column reaches
  `jsonable_encoder`" gap (checked all of `api/routes/`).

## **Testing requirements**

- `tests/api/test_classifications.py::test_correct_classification_with_stored_embedding_serializes_response`
  -- regression test that sets a non-UTF-8 `embedding` blob on the classification (reproducing
  the exact byte from the reported traceback) and asserts a 200 with the expected body, so this
  can't silently regress the way it shipped originally.
- Full `./scripts/check.sh` passes (ruff, pytest, `npm run build`, `npm run lint`).

## **Dependencies**

None.

## **Suggested commit message**

`fix(DT-1109): stop /classifications/{id}/correct 500ing on embedding blobs`
