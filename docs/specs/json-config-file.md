# JSON Configuration File

## Purpose

All application configuration today is flat environment variables, loaded by
`immich_dog_tagger.config.load_config()` from a `.env` file (via `python-dotenv`) or the
container's `environment:` block. That works well for scalar settings (a URL, a timeout, a
numeric tuning knob), but [multi-Immich-account support](multi-immich-account-sync.md) needs to
declare a *list* of (account name, API key) pairs -- structured data flat environment variables
have no native way to express. The candidates considered there (a JSON string crammed into one
`IMMICH_ACCOUNTS` env var, or an ad hoc numbered-variable convention like `IMMICH_API_KEY_1`/
`IMMICH_API_KEY_2`) are both worse to read, write, and validate than just writing structured
configuration as structured data.

This spec introduces a JSON configuration file, mounted into the container as a bind-mounted
volume (the same pattern `docker-compose.yml` already uses for `state`, `cache`, and `models`
directories), as the home for this kind of configuration going forward -- and reviews every
existing environment variable to decide, one at a time, whether it belongs there or should stay an
environment variable.

## User story

As an operator, I want to configure the parts of this app that are naturally structured data (like
a list of Immich accounts) in a single JSON file I edit and mount into the container, instead of
inventing my own encoding to cram structured data into flat environment variables, so
configuration stays easy to read, edit, and keep under version control.

## Goals

- Introduce a JSON configuration file as a new configuration source, loaded by (a successor to)
  `load_config()`.
- Give [multi-Immich-account support](multi-immich-account-sync.md) a natural home for its
  account list: `{"name": ..., "api_key": ...}` objects in a JSON array, not a stringified env var.
- Review every existing environment variable (below) and decide whether it moves into the JSON
  file or stays where it is.
- Ship a documented example file (mirroring `.env.example`'s role today) and update
  `docker-compose.yml`, `docs/deployment.md`, and the README.
- An existing deployment with no config file at all keeps working exactly as it does today --
  this is an additive, opt-in configuration source, not a breaking replacement.
- A missing required field or malformed file fails fast at startup with a message naming the file
  and the exact problem, rather than a downstream error the first time the value is used.

## Non-goals

- **Live reload.** A config file change needs a container restart to take effect, same as an
  environment variable change today.
- **Moving `docker-compose.yml`'s own host-path variables** (`HOST_STATE_DIR`, `HOST_CACHE_DIR`,
  `HOST_MODEL_DIR`) into the JSON file. This is impossible in principle: docker-compose needs
  these to resolve its own `volumes:` section *before* the container -- and therefore the mounted
  config file -- exists. They stay in `.env`/the shell environment that runs `docker compose up`.
- **A web UI for editing this file.** Consistent with today's design (Immich credentials and
  deployment config are never editable from the app's own UI, only environment-configured).
- **Encrypting secrets at rest.** The file contains one or more Immich API keys in plaintext, the
  same exposure `.env` already has today; host-level file permissions remain the operator's
  responsibility, unchanged from the current model.
- **A generalized settings/plugin system.** This is a fixed, documented schema for this app's own
  configuration, not an extensible or user-defined config format.
- **Moving `CROP_PADDING`.** It's a pipeline tuning knob, not deployment topology or an
  Immich-connection detail -- less obviously in-scope than the `immich.*` settings, and low-stakes
  either way. Stays an environment variable; revisit only if more pipeline knobs accumulate and a
  `pipeline` object earns its keep.
- **One-shot migration tooling.** No `immich-dog-tagger migrate-config` command that writes a
  `config.json` from the current environment. Hand-authoring the (short) JSON file from
  `config.example.json` is enough for FR-2's backward compatibility to hold without it; revisit if
  migration friction turns out to matter in practice.

## Reviewing the existing environment variables

| Variable | Today | Decision | Why |
| --- | --- | --- | --- |
| `IMMICH_URL` | required env var | moves to JSON (`immich.url`) | Structural Immich config; naturally sits alongside the new accounts array. |
| `IMMICH_EXTERNAL_URL` | optional env var | moves to JSON (`immich.external_url`) | Same category as `IMMICH_URL`; the two are already documented together. |
| `IMMICH_API_KEY` | required env var (single account) | superseded by JSON (`immich.accounts: [{name, api_key}, ...]`) | The reason this spec exists -- see [multi-Immich-account-sync.md](multi-immich-account-sync.md). Legacy `IMMICH_API_KEY` keeps working as a fallback (see Requirements) so nothing breaks for an install that never adopts the file. |
| `IMMICH_TIMEOUT_SECONDS` | optional env var, default `60` | moves to JSON (`immich.timeout_seconds`) | Same "how this app talks to Immich" category as the URL/accounts. |
| `CROP_PADDING` | optional env var, default `0.15` | stays an environment variable | See Non-goals. |
| `STATE_DIR` | env var (fixed by `docker-compose.yml` to `/app/state` in the packaged deployment; user-set when running from source) | stays an env var | Tied to how/where the process is launched (container vs. source checkout), not "application configuration" -- and something has to name *this* file's own location without depending on it, which an env var already does today for other paths. |
| `CACHE_DIR` | same as `STATE_DIR` | stays an env var | Same reasoning. |
| `YOLO_MODEL` | same as `STATE_DIR` | stays an env var | Same reasoning. |
| `HOST_STATE_DIR` / `HOST_CACHE_DIR` / `HOST_MODEL_DIR` | docker-compose-only vars (never read by the Python app) | stays in `.env` | Consumed by `docker compose` itself for `volumes:` substitution before the container exists; see Non-goals. |
| `GIT_COMMIT` | env var baked in at image build time | stays an environment variable | Build/CI metadata, not operator configuration. |

The practical effect: a new `CONFIG_FILE` environment variable (see Resolved decisions for its
default paths) tells the app where to find the JSON file. Everything under `immich.*` moves there;
filesystem/runtime-launch paths and docker-compose's own host-mount variables do not.

## Requirements

- **FR-1: File format and location.** A JSON file with (at minimum) an `immich` object:
  `{"immich": {"url": "...", "external_url": "...", "timeout_seconds": 60, "accounts": [{"name": "...", "api_key": "..."}]}}`.
  Its path is given by the `CONFIG_FILE` environment variable; `docker-compose.yml` mounts a host
  file to that path as a new bind-mounted volume, the same pattern used for
  `HOST_STATE_DIR`/`HOST_CACHE_DIR`/`HOST_MODEL_DIR`.
- **FR-2: Backward compatibility.** If `CONFIG_FILE` is unset, or the path it names isn't an
  existing regular file, configuration loading falls back to today's legacy environment variables
  (`IMMICH_URL`/`IMMICH_API_KEY`/`IMMICH_EXTERNAL_URL`/`IMMICH_TIMEOUT_SECONDS`) exactly as it
  works today, producing a single implicit account. An existing deployment needs zero changes to
  keep working after upgrading to a build that includes this feature. This check is deliberately
  "is a file", not "exists": a Docker bind mount whose host source doesn't exist yet is
  auto-created as a directory, and that must be treated the same as "no config file" rather than
  raising a confusing `IsADirectoryError`.
- **FR-3: Validation.** Malformed JSON, a missing required field (`immich.url`; at least one
  account with a `name` and `api_key`), or a duplicate account name fails startup immediately with
  a message naming the file path and the specific problem -- never a stack trace, and never
  silently falling back to legacy env vars when a config file was clearly intended but is broken.
- **FR-4: Precedence and transparency.** If both a config file and legacy environment variables
  are present at once (e.g. mid-migration), the config file wins outright, and a startup log line
  states that the legacy environment variables were present but ignored -- so an operator
  mid-migration is never left guessing which source is actually in effect.
- **FR-5: Documentation and examples.** A `config.example.json` (mirroring `.env.example`'s role)
  ships in the repo; `docker-compose.yml`, `docs/deployment.md`, and the README are updated to
  show mounting it, and to describe migrating from the legacy `IMMICH_*` environment variables.

## Acceptance criteria

- Given an existing deployment with only `.env`/`docker-compose.yml` environment variables set
  (no `CONFIG_FILE`/mounted JSON), the app starts and behaves exactly as before.
- Given a `config.json` declaring two Immich accounts, configuration loading exposes both accounts
  with no `IMMICH_API_KEY` environment variable needed at all.
- Given a `config.json` missing `immich.url`, or with zero accounts, or with two accounts sharing
  the same name, startup fails immediately naming the file and the specific missing/invalid field
  -- not a later error during scan/sync.
- Given both a `config.json` and a legacy `IMMICH_API_KEY` environment variable set, the accounts
  from `config.json` are used, and the startup log states that the environment variable was
  ignored.
- Given a `CONFIG_FILE` path that doesn't exist, startup proceeds on the legacy environment-variable
  path with no error (this is the expected "hasn't migrated yet" state, not a misconfiguration).

## Out of scope

Declaring the actual multi-account *behavior* (scan/download/sync per account, shared
classification) -- that's [#346](https://github.com/bradreimer/immich-dog-tagger/issues/346),
which depends on this story landing first. This spec only makes the account list loadable and
exposes it on `Config.accounts`; nothing yet reads more than the first account
(`Config.immich_api_key`, unchanged, is the first account's key).

## Resolved decisions

These were open questions when this spec was written; resolved during implementation
([#348](https://github.com/bradreimer/immich-dog-tagger/issues/348)):

- **Naming and default paths.** `CONFIG_FILE` was kept as proposed. There is no built-in default
  path in the application itself -- an unset `CONFIG_FILE` means "no config file", full stop, so a
  stray `config.json` in a source checkout's working directory can never be picked up by
  surprise. `docker-compose.yml` sets `CONFIG_FILE=/app/config/config.json` for the container and
  mounts `${HOST_CONFIG_FILE:-./data/config.json}` there (empty by default, matching FR-2's
  auto-created-directory case); running from source, an operator opts in by setting
  `CONFIG_FILE=./config.json` (or any path) in `.env` themselves.
- **Exact JSON schema.** Settled as proposed: `{"immich": {"url", "external_url",
  "timeout_seconds", "accounts": [{"name", "api_key"}]}}`. `external_url` and `timeout_seconds`
  are optional (default `""` and `60`, mirroring the legacy environment variables' defaults).
