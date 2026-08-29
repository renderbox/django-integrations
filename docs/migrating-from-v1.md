# Migrating from v1

v1's `Credential` model had provider-shaped columns
(`client_id`, `client_url`, `public_key`, `private_key`, `attrs`) with no
way to tell which provider a row actually belonged to except by
convention - which columns happened to be populated, plus a free-text
`name` field.

v2 adds `integration` (a slug), `config` (plain JSON), and `secrets`
(encrypted JSON) to the *same* `Credential` table, alongside the
untouched legacy columns. **No existing row data is migrated
automatically** - this is a deliberate, structural decision, not a gap
to be filled in later: v1 stores no integration/slug identifier
anywhere, so there is no reliable, generic way to know which provider a
given legacy row belongs to. Migrating actual data is necessarily
application-specific.

## If you're backfilling data yourself

The natural per-field mapping, once *you've* determined which
integration a given row represents:

| v1 column | v2 destination |
|---|---|
| `client_id` | `config["client_id"]` (rename to match your field's actual name) |
| `client_url` | `config["client_url"]` |
| `public_key` | `secrets["public_key"]` |
| `private_key` | `secrets["private_key"]` |
| `attrs` | **do not auto-migrate** - see below |

Go through `services.save_config()` (see
[configuration-and-secrets.md](configuration-and-secrets.md)) rather
than writing to `config`/`secrets` directly - it validates against the
target integration's actual field schema. In particular, `client_url`
was never validated as a real URL in v1 (a plain `CharField`); if your
integration's schema declares that field a `URLField`, re-validate
through `save_config()` rather than trusting the old string as-is.

### `attrs`

v1's `attrs` is an arbitrary JSON blob with no indication of which keys,
if any, are sensitive. There is no safe, generic rule for splitting it
into `config` vs `secrets` automatically - do not write code that
guesses. Classify each key by hand, for each application, based on
actual knowledge of what was stored there.

## What else changed

- `Credential.site`'s reverse accessor is now `site.credentials` (was
  `site.site` - confusing, and unrelated to any migration concern, just
  fixed while touching the model).
- `(site, integration)` has a uniqueness constraint - one `Credential`
  per site per integration slug. `integration` is nullable specifically
  so this doesn't affect existing rows (SQL treats multiple `NULL`s as
  non-conflicting), including sites that already have several legacy
  rows with different provider data in them.
- The legacy `EncryptedTextField` (`public_key`/`private_key`) used to
  silently return raw ciphertext if it couldn't be decrypted with any
  configured key. It now raises `DecryptionError` instead - see
  [encryption.md](encryption.md).

Legacy columns aren't going anywhere yet - removing them is a separate,
deliberate decision (Phase 13 in this project's own rewrite plan) made
only once a real compatibility window has been decided, not a side
effect of v2 landing.
