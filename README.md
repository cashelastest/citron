# Mini Ledger — Idempotent Transfers & Clean Architecture

A small, production-oriented ledger service: merchants hold balances in multiple
currencies and transfer funds between each other with idempotent execution,
per-transfer fees, and correct behavior under concurrent requests.

Built with FastAPI, SQLAlchemy 2.0 (async), PostgreSQL and Alembic.

## Contents

- [Quick start](#quick-start)
- [API examples](#api-examples)
- [Architecture](#architecture)
- [Idempotency design](#idempotency-design)
- [Concurrency strategy](#concurrency-strategy)
- [Multi-currency handling](#multi-currency-handling)
- [Fees](#fees)
- [Error handling](#error-handling)
- [Testing](#testing)
- [Known limitations & possible improvements](#known-limitations--possible-improvements)

## Quick start

```bash
docker-compose up --build
```

This starts Postgres and the API. The API container waits for Postgres'
healthcheck, then runs `alembic upgrade head` automatically before starting
`uvicorn` (see `CMD` in `Dockerfile`) — no manual migration step needed.

The API is then available at `http://localhost:8000`, interactive docs at
`http://localhost:8000/docs`.

### Running the test suite

Tests hit a **real** Postgres database (not SQLite — the whole point of the
concurrency tests is to exercise `SELECT ... FOR UPDATE` and `NUMERIC(20,8)`,
neither of which SQLite enforces the same way). `tests/conftest.py` drops and
recreates the test database and runs the Alembic migrations for you on every
run — you only need to point it at a reachable Postgres server that has
CREATEDB rights.

If you use the Compose Postgres for this (`docker-compose up -d db`), remember
it's exposed on host port **5433**, not 5432:

```bash
docker-compose up -d db
export TEST_DATABASE_URL=postgresql+asyncpg://ledger_user:ledger_pass@localhost:5433/citron_test
pip install -r requirements-dev.txt
pytest -v
```

## API examples

**Create a merchant**

```bash
curl -X POST http://localhost:8000/merchants \
  -H "Content-Type: application/json" \
  -d '{"merchant_name": "alice_store", "currency": "BTC", "initial_balance": "0.00001"}'
```

**Get a merchant**

```bash
curl http://localhost:8000/merchants/alice_store
```

**Get a merchant's balances**

```bash
curl http://localhost:8000/merchants/alice_store/balance
```

**Execute a transfer** — the `Idempotency-Key` header is required; sending the
same key again returns the original result instead of moving money twice.

```bash
curl -X POST http://localhost:8000/transfers \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: abc-123-xyz" \
  -d '{"from_merchant": "alice_store", "to_merchant": "bob_shop", "currency": "BTC", "amount": "0.000005"}'
```

**List transfers, filtered**

```bash
curl "http://localhost:8000/transfers?from=alice_store&currency=BTC"
```

## Architecture

The codebase is split into three layers with a one-directional dependency
rule — inner layers never import from outer ones:

```
app/
├── api/              # HTTP boundary — FastAPI routes, Pydantic schemas, error mapping
│   ├── routes/        (thin: parse input, call a service, return the result)
│   ├── schemas/        Pydantic request/response models, HTTP-only concerns
│   ├── exception_handlers.py   translates DomainError -> HTTP status + JSON
│   ├── middleware.py            request-id tagging for logs
│   └── deps.py                  FastAPI dependency wiring (composition root)
│
├── domain/           # business logic — no FastAPI or SQLAlchemy imports
│   ├── services/       TransferService, MerchantService, FeeCalculator
│   ├── models/          plain dataclasses used as inputs/outputs of services
│   ├── exceptions.py    DomainError hierarchy (error_code + status_code)
│   └── enums/
│
└── infrastructure/   # persistence — the only layer that knows about SQLAlchemy
    ├── models/          ORM table definitions
    ├── repositories/    one repository per aggregate (Merchant, Balance, Transfer)
    ├── unit_of_work.py  groups repositories behind one DB transaction
    └── db.py             async engine/session setup
```

Routes never contain business rules — they build a request object, call a
service method, and return whatever the service gives back. Services never
import SQLAlchemy — they talk to the database only through repository
interfaces exposed by `UnitOfWork`. Repositories are the only place that
knows about the actual table structure and are also where locking and
conflict-handling (`SELECT ... FOR UPDATE`, `ON CONFLICT`) live, since that's
inherently a persistence concern.

Request/response shapes are deliberately **not** reused between layers: the
API's `TransferCreateRequest` (Pydantic) is mapped explicitly, field by field,
into the domain's `TransferRequest` in the route handler. This costs a few
extra lines but means the domain layer has no dependency on how a request
happened to arrive over HTTP, and API-level renames/aliases never leak into
business logic.

## Idempotency design

- The `Idempotency-Key` header is required on `POST /transfers` and is stored
  as a **unique column** (`transfers.idempotency_key`).
- Before doing anything else, `TransferService.execute_transfer` checks
  whether a transfer with that key already exists. If it does, it returns the
  stored result immediately — no funds are touched.
- If it doesn't exist yet, the transfer executes normally: merchants are
  resolved, the fee is computed, balances are moved, and finally a `Transfer`
  row is inserted with that idempotency key.
- **Race on the same key:** if two requests with an identical key arrive at
  the same time, both may pass the initial "does it exist" check before
  either has committed. Both will attempt the balance move and the insert;
  the loser's `INSERT` hits the unique constraint on `idempotency_key`.
  `TransferRepository.create` translates that `IntegrityError` into a
  domain-level `DuplicateIdempotencyKeyError`, which the service catches to
  roll back (discarding that request's balance changes), re-read the row the
  winner just committed, and return *that* — so both requests converge on the
  same response and money moves exactly once. This is verified in
  `tests/test_idempotency.py` with concurrent `asyncio.gather` calls, not
  just sequential retries.
- The pre-flight lookup is only a fast path. The unique constraint is the
  actual source of truth, which is why correctness does not depend on the
  check winning the race.

## Concurrency strategy

Balances must never go negative and must never be double-spent, even when the
same merchant is involved in several transfers at once. Two layers of
defense:

1. **Database-level `CHECK (amount >= 0)` constraint** on `balances.amount` —
   a hard backstop that fires even if application logic is ever bypassed or
   has a bug.
2. **Row-level pessimistic locking** in `BalanceRepository.move()`:
   - Both the sender's and receiver's balance rows are locked with
     `SELECT ... FOR UPDATE` inside the same DB transaction before any
     amount is checked or changed.
   - The two rows are locked **in a fixed order — sorted by merchant ID**,
     regardless of who is sender and who is receiver. This is what prevents
     deadlocks: without it, a transfer A→B and a concurrent transfer B→A
     could each hold one lock and wait forever for the other. With a global
     lock order, one of them always acquires both locks first and the other
     simply queues. Covered by `test_opposite_transfers_do_not_deadlock`.
   - The insufficient-funds check (`amount + fee`) happens only *after* the
     row is locked, so a second concurrent transfer can't slip in between
     the check and the debit.
3. **Opening a new currency balance** (first transfer a merchant receives in
   a currency it's never held) uses `INSERT ... ON CONFLICT DO NOTHING`
   instead of check-then-insert, so two concurrent transfers opening the same
   new balance don't abort each other on the unique `(merchant_id, currency)`
   constraint.
4. **Uniqueness races end as domain errors, not 500s.** Both unique
   constraints in the schema — `merchants.merchant_name` and
   `transfers.idempotency_key` — are caught in the repository that owns the
   insert and re-raised as `MerchantAlreadyExistsError` (409) and
   `DuplicateIdempotencyKeyError` respectively. The service-level
   `exists()` check before creating a merchant is a fast path for the common
   case; under concurrency it is the constraint, not the check, that holds.

Translating driver exceptions inside the repository is deliberate: it keeps
`app/domain/` free of any SQLAlchemy import, so the service layer only ever
handles domain types.

All of this is exercised against a **real** Postgres instance in tests (see
`tests/test_concurrency.py`), including firing many concurrent transfers at
the same sender to prove the balance never dips below zero and never loses an
update.

## Multi-currency handling

A merchant can hold any number of currency balances; there's no fixed list of
supported currencies. `balances` is keyed by `(merchant_id, currency)` with a
uniqueness constraint. A merchant is created with one initial balance; any
further currency is opened lazily the first time that merchant is on the
receiving end of a transfer in a currency it doesn't hold yet (starting at
zero, see `ensure_exists` above). Currency codes are normalized to uppercase
on input so `"btc"` and `"BTC"` resolve to the same balance. All amounts use
`NUMERIC(20, 8)` in Postgres and Python `Decimal` end to end — never `float`
— to avoid rounding/precision issues with money.

## Fees

Fees are calculated by `FeeCalculator`, kept as its own class (rather than
inlined in `TransferService`) so the fee *policy* can change — flat fee,
per-currency rate, min/max caps — without touching the transfer flow itself.

- Current policy: a flat percentage of the transfer amount, configured via
  the `FEE_PERCENT` environment variable (default `0.01` = 1%).
- The fee is rounded with `ROUND_HALF_UP` to 8 decimal places.
- The **sender** pays `amount + fee`; the **receiver** is credited exactly
  `amount`. Both figures, plus the computed fee, are stored on the `Transfer`
  row and returned in the API response, so the fee is always auditable
  after the fact rather than only visible at calculation time.
- Insufficient-funds checks are always against `amount + fee`, never against
  `amount` alone.

## Error handling

All expected failures raise a typed `DomainError` subclass
(`app/domain/exceptions.py`), each carrying its own `error_code` and HTTP
`status_code` (e.g. `merchant_not_found` → 404, `insufficient_funds` → 402,
`same_merchant_transfer` → 400). A single exception handler
(`app/api/exception_handlers.py`) turns these into a consistent JSON body:

```json
{
  "error": "insufficient_funds",
  "message": "Insufficient funds: required 0.00001010 BTC, available 0.00000500 BTC",
  "details": { "currency": "BTC", "required": "0.00001010", "available": "0.00000500" }
}
```

Anything unexpected falls through to a generic 500 handler rather than
leaking a stack trace to the client. Input validation errors (missing
fields, negative amounts, malformed currency codes) are caught by Pydantic
at the schema level before they ever reach the domain.

## Testing

Run with `pytest -v`. Coverage includes:

- `test_idempotency.py` — same-key retries (sequential and concurrent),
  different keys producing different transfers, key validation.
- `test_transfers.py` — main transfer flow, fee deduction, insufficient
  funds (including the fee in the required amount), self-transfer rejection,
  unknown merchant/currency, listing with filters.
- `test_merchants.py` — creation, duplicate names, validation, balance
  lookups.
- `test_fee_calculator.py` — pure unit tests of rounding behavior, no DB.
- `test_concurrency.py` — many simultaneous transfers against one balance to
  prove no negative balance and no lost updates; opposite-direction transfers
  to prove no deadlock; concurrent opening of a new currency balance.

Each test runs against a freshly truncated database (`clean_tables` fixture)
rather than a transaction rollback, specifically because the concurrency
tests need several real, separately-committing connections to actually see
each other's changes.

## Known limitations & possible improvements

- **Idempotency key reuse with a different body isn't detected.** Replaying
  the same key with a different `amount`/`to_merchant` silently returns the
  original transfer instead of rejecting the mismatch. Stricter idempotency
  (à la Stripe) would hash/store the original request payload and compare it
  on replay.
- **No authentication/authorization** — out of scope for this exercise, but
  a real deployment needs it before any endpoint is reachable outside a
  trusted network.
- **No pagination** on `GET /transfers` — fine at test scale, would need
  cursor/offset pagination under real volume.
- **Fee policy is a single global percentage.** The `FeeCalculator`
  abstraction is already in place to support per-currency rates or tiered
  fees without touching `TransferService`, but only the flat-rate
  implementation exists today.
- **No outbox/event log.** A ledger like this would typically also emit an
  immutable event per balance change for audit/replay purposes, independent
  of the current-state `balances` table.