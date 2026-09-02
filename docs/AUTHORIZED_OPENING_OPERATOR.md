# Authorized-opening operator workflow

This is a local, owner-operated intake and review path. It is not a public
form, browser UI, social collector, or auto-approval mechanism. Social
discovery can identify candidates for separate activity reporting, but it can
never be promoted through this intake command.

## Inputs and credentials

The submit command accepts exactly one explicitly supplied creator/owner
evidence-envelope JSON file. The file must be a regular file with mode `0600`;
the CLI opens it without following symlinks, reads at most 16 KiB, validates
the exact `1.0.0` camel-case schema locally, and does not write or persist its
contents. The envelope contains only bounded opening facts and owner-produced
opaque HMAC-SHA-256 references. It must not contain a URL, social-platform ID,
raw evidence, author identity, media, cookie, or credential.

Store the two dedicated PostgreSQL URLs in a separate environment file outside
the repository with mode `0600`:

```text
AUTHORIZED_OPENING_SUBMITTER_DB_URL=postgresql://...
AUTHORIZED_OPENING_REVIEWER_DB_URL=postgresql://...
```

The CLI never falls back to `SUPABASE_DB_URL` or a service-role key. The
submitter URL must use the named `NOINHERIT` login
`pokecrack_authorized_opening_submitter_login`. The reviewer URL may use the
one owner-provisioned reviewed `NOINHERIT` login selected for the deployment;
the CLI attests that login after connecting. Both URLs require TLS
(`sslmode=require`, `verify-ca`, or `verify-full`) and must pin the
corresponding role with exactly
`options=-c role=pokecrack_authorized_opening_submitter` or
`options=-c role=pokecrack_authorized_opening_reviewer`. Do not put either URL
in command arguments, shell history, logs, Git, or chat.

The migration creates the `NOLOGIN NOINHERIT` capability role and grants only
the direct-only submit wrapper. An account owner may provision one separate
reviewer login outside the migration; its username is intentionally not a
security allowlist. The login must itself be `NOINHERIT`, non-superuser,
non-`CREATEROLE`, non-`CREATEDB`, non-replication, `NOBYPASSRLS`, connection
limit `2`, and must receive the capability only through a non-admin membership
with `INHERIT FALSE, SET TRUE`. Generate and rotate its password out of band.

## Submit an owner envelope

Create the envelope in a private temporary directory, set mode `0600` before
writing any fields, and remove it after the command. The following is a
workflow sketch; fill the envelope from the owner-controlled evidence process,
not from social discovery or a generic fetcher:

```bash
umask 077
work_dir="$(mktemp -d -t pokecrack-authorized-opening.XXXXXX)"
envelope_path="$work_dir/envelope.json"
touch "$envelope_path"
chmod 600 "$envelope_path"
# Write the exact owner envelope to "$envelope_path" using the approved local
# evidence process. Never include raw evidence or a URL in that JSON file.

pokecrack-worker authorized-opening submit "$envelope_path"

rm "$envelope_path"
rmdir "$work_dir"
```

On success the only returned fields are `submission_id`, `revision`, and
`state`. URL/URI syntax is rejected in every string field before any database
call, and malformed, non-private, social-derived, or unauthorized envelopes
fail closed. The submitter role reaches a database direct-only wrapper
(`ingest.submit_authorized_opening_direct_v1`) and cannot call the historical
service-role submit RPC directly. Database and protocol failures are reduced
to safe error codes; the CLI never prints the input path, DSN, password, opaque
hash, or evidence.

## Review and retract

Use the separate reviewer environment and login. Queue output is deliberately
redacted to `submission_id`, `revision`, and `state`:

```bash
pokecrack-worker authorized-opening list-reviews --state queued --limit 50
pokecrack-worker authorized-opening review SUBMISSION_UUID \
  --expected-revision 1 \
  --target-state in_review \
  --reason-code review_started \
  --reviewer-reference-sha256 LOWERCASE_64_HEX_REFERENCE
pokecrack-worker authorized-opening review SUBMISSION_UUID \
  --expected-revision 2 \
  --target-state accepted_statistics \
  --reason-code evidence_verified \
  --reviewer-reference-sha256 LOWERCASE_64_HEX_REFERENCE
pokecrack-worker authorized-opening retract OBSERVATION_UUID \
  --reason-code privacy_request \
  --reviewer-reference-sha256 LOWERCASE_64_HEX_REFERENCE
```

The review RPC owns the row lock, revision fence, expiry check, duplicate
gate, and immutable observation/event writes. The CLI performs only local
shape checks and calls the typed RPCs; it never writes an ingest table. A
reviewer must independently verify authorization, evidence completeness,
geography, and denominator before choosing an acceptance state. There is no
auto-approval path.

An accepted-statistics review also returns the safe canonical
`accepted_observation_id` UUID. Copy that UUID to the retract command when a
later takedown is required. This identifier is the only observation detail
returned; reviewer references, evidence hashes, and raw evidence remain
redacted.

The retraction result contains only the accepted observation UUID, safe reason
code, and a `retracted` state. It does not reveal references or evidence.

## Explicit limitations

This vertical slice is local and forward-only. It does not apply migrations,
provision credentials, fetch evidence, validate external URLs, operate a
browser/social account, or publish an aggregate. Apply the migration only via
the separately reviewed owner migration workflow, then verify the role ACL and
the dedicated login on an isolated PostgreSQL 17/Supabase environment before
using a real envelope.
