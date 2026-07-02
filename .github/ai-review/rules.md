# sbc-pay review rules

## Exception handling
- Never catch bare `Exception` without logging the full traceback via `current_app.logger.error` or `capture_message`
- Do not swallow exceptions silently (bare `except: pass` or `except Exception: pass`)
- Payment-state transitions that fail must roll back — never leave an invoice in a partial state

## Testing
- Every new service method requires at least one negative-path unit test (invalid input, external service failure, forbidden state transition)
- Do not mock the database in integration tests — use the real test DB (past incident: mock/prod divergence masked a broken migration)
- New payment flow tests must assert the final invoice status, not just the absence of an exception

## Security
- No account numbers, bank numbers, or PAD details in log output (they are AES-encrypted at rest — logging them plaintext defeats that)
- No secrets or credentials in code, config files, or test fixtures
- IAM / permission checks (`check_auth`) must not be weakened or bypassed
- CI weakening is a blocker: removed tests, added `|| true`, skipped lint, or `ALLOW_SKIP_PAYMENT=True` in non-dev config

## Dependencies
- If `pyproject.toml` changes, `poetry.lock` must also be updated — a pyproject change without a lock update means the lockfile is stale
- A `poetry.lock`-only change is normal (transitive dependency updates) — do not flag it
- Flag any new dependency that introduces network calls, file system access, or subprocess execution

## Payment logic
- Invoice status transitions must follow the allowed state machine — flag any direct status assignment that skips `InvoiceStatus` enum checks
- `PaymentSystemFactory.create()` must be used for payment method selection — do not instantiate payment services directly
- EFT and PAD flows touch bank account data — changes here need extra scrutiny
