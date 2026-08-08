# DT-0908

## ID
DT-0908

## Related spec
v0.9.0 Mission Control Foundation

## Priority
High

## Status
Completed

## Goal
Make CLI pipeline operations use the same shared job runner as Mission Control.

## Context
There must be one execution path for pipeline operations. The CLI remains useful for maintenance, scripting, and recovery, but must not become a second implementation of orchestration.

## Implementation notes
- Inspect existing CLI command behavior before changing it.
- Route scan, detect, embed, classify, learn, sync, and full-pipeline execution through the shared job infrastructure where applicable.
- Preserve existing CLI arguments and user-visible behavior unless there is a concrete reason to change them.
- Ensure CLI exit codes remain meaningful.
- Do not make the CLI depend on the browser or a running web server.

## Acceptance criteria
- CLI operations use the shared pipeline runner.
- Existing CLI workflows remain functional.
- CLI failures produce appropriate non-zero exit status.
- A job created by the CLI is visible through the same job API/UI.
- No duplicate pipeline implementation exists between CLI and web execution.

## Testing requirements
- CLI regression tests.
- Job integration tests.
- Exit-code tests.
- End-to-end test covering a representative CLI operation.

## Dependencies
DT-0902

## Suggested commit message
`refactor(cli): execute pipeline commands through job runner`
