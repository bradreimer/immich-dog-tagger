# Immich API key permissions

This app talks to Immich only through a single API key (`IMMICH_API_KEY` in `.env`). Immich's API
keys support granular, per-permission scoping, and it's easy to create one that's missing exactly
the permission Sync needs to actually attach photos to a tag or album -- Immich will still report
success for most of the request, so the failure isn't always obvious. This page lists exactly
which permissions to grant.

## Where to create the key

In Immich: **Account Settings → API Keys → New API Key**. Give it a name (e.g. `dog-tagger`) and
check the permissions below, or select **Full access** if you're comfortable granting this app
everything Immich exposes (more than it needs).

## Required permissions

| Permission | Used for |
|---|---|
| `asset.read` | Scanning your library (`scan`) |
| `asset.download` | Downloading photos for detection/classification (`download`) |
| `album.read` | Finding each pet's existing album (`sync`) |
| `album.create` | Creating a pet's album the first time it's synced (`sync`) |
| `albumAsset.create` | Adding photos to a pet's album (`sync`) |
| `albumAsset.delete` | Removing photos from a pet's album when a correction moves them elsewhere (`sync`) |
| `tag.read` | Finding each pet's existing tag (`sync`) |
| `tag.create` | Creating a pet's tag the first time it's synced (`sync`) |
| `tag.asset` | Tagging/untagging photos with a pet's tag (`sync`) |

Immich's "New API Key" screen groups these as checkboxes by resource (Asset, Album, Album Asset,
Tag, ...) -- check each permission listed above, or check the whole **Album**, **Album Asset**,
**Tag**, and the `Read`/`Download` **Asset** checkboxes.

## Troubleshooting: Sync creates albums/tags but no photos end up in them

If Sync reports identities synced (or the CLI/job output says "failed to sync N identity/ies")
but photos aren't actually showing up in the corresponding Immich album or tag, the API key is
almost always missing one of the permissions above -- most often `tag.asset`, since Immich tags
are private to the owning user and aren't shareable the way albums are, so a key that works fine
for albums can still be rejected for tags.

Immich reports this as a per-photo `no_permission` result on an otherwise-successful HTTP
request, rather than an outright request failure, so it doesn't look like a typical error. Sync
detects this case specifically and calls it out in its output/progress message with a link back
to this page (issue [#259](https://github.com/bradreimer/immich-dog-tagger/issues/259)). The
affected identity's previous Immich membership is left untouched and retried on every subsequent
sync, so fixing the key's permissions and re-running `sync` is enough -- no manual cleanup needed.
