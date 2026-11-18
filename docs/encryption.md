# Encryption and key rotation

Every stored secret - the new `Credential.secrets` JSON field and the
legacy `public_key`/`private_key` columns - is encrypted at rest with
[Fernet](https://cryptography.io/en/latest/fernet/) symmetric encryption,
configured entirely through one setting:

```python
ENCRYPTED_FIELD_KEYS = [
    "gAAAAA...",  # primary - encrypts new/updated values
    "gAAAAA...",  # older keys - only used to decrypt existing data
]
```

The **first** key is always the primary key: it's what new writes are
encrypted with. Every key in the list is tried when decrypting, in
order - that's what makes rotation possible without a flag day.

Keys are resolved fresh on every read/write, not cached or bound once at
startup - so changing this setting (including via `@override_settings`
in tests) takes effect immediately.

If a stored value can't be decrypted with any configured key, reading it
raises `DecryptionError` rather than silently returning the ciphertext
as if it were usable - this is the property that makes rotation safe to
reason about: a genuinely undecryptable value is a loud failure, not a
corrupted-looking secret quietly used somewhere.

## Rotating keys

1. **Add the new key to the front of `ENCRYPTED_FIELD_KEYS`.** It's now
   the primary key. Keep the old key(s) in the list so existing data
   still decrypts.
2. **Run the rotation command:**

   ```bash
   python manage.py rotate_encryption_keys
   ```

   This walks *every* installed model with an `EncryptedTextField` or
   `EncryptedJSONField` - not just this package's own `Credential` - and
   re-encrypts every row with the current primary key. It re-reads each
   row after writing to confirm the rewrite actually round-tripped,
   rather than assuming success, and reports any mismatch as an error
   instead of continuing silently.
3. **`--dry-run` first if you want to see what would change** without
   writing anything:

   ```bash
   python manage.py rotate_encryption_keys --dry-run
   ```
4. **Verify**, then remove the retired key from `ENCRYPTED_FIELD_KEYS`.
   Everything was re-encrypted with the new primary key in step 2, so
   nothing needs the old key anymore.

## System check

`manage.py check` validates `ENCRYPTED_FIELD_KEYS` itself
(`integrations.E006`) - missing entirely, or containing something that
isn't a valid Fernet key, is caught there rather than only surfacing the
first time something tries to actually encrypt or decrypt a value.
