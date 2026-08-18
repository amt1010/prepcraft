# SaaS Tiers, Auth, and Billing — Design

## Goal

Turn the AI Practice Paper Generator from a local CLI pipeline into a
metered, tiered, paid product: guests get a small free taste by IP,
registered users get a bit more, paying subscribers (monthly or annual)
get substantially more — and every number involved (quotas, prices) is
editable by an admin without a code deploy.

This is a second initiative alongside the pipeline work in PROJECT_PLAN.md
— being built in parallel, per the decision below, not after the pipeline
is finished.

## Decisions made during brainstorming

- **Sequencing:** build the SaaS layer in parallel with the pipeline, not
  after it.
- **Scan unit:** one scan = one page/image uploaded (not one paper as a
  whole). This is itself admin-configurable (per-page vs. per-paper) —
  start with per-page.
- **PDF generation unit:** one unit = one generated paper (question paper
  + answer sheet together), not two.
- **Quota reset:** rolling 30 days per identity (not calendar month) — a
  guest's window starts at their first scan on that IP; a user's window
  starts at their first scan on that account.
- **Guest -> registered:** registering gives an independent fresh quota
  bucket tied to the account. Prior guest usage on that IP does not carry
  over or offset it.
- **Annual tier quota cadence:** annual subscribers' scan/PDF limits reset
  every month, same as monthly subscribers — paying annually changes
  billing cadence and (typically) the monthly limit's generosity, not how
  often the quota resets. Concrete numbers (30/30, 100/100, etc.) are
  admin-configurable placeholders, not fixed.
- **Over-quota behavior:** hard block with an upgrade prompt. No partial
  processing.
- **Default seed quotas:** every tier (guest, registered_free,
  subscribed_monthly, subscribed_annual) ships with `scans_per_period = 2`
  and `pdfs_per_period = 2` at first deploy — a uniform starting point the
  admin then differentiates per tier through the `/admin` UI. Not a
  hardcoded default in code; it's the seed data in the `Tier` table's
  first migration, editable the same way as any later change.
- **Billing provider:** deferred behind an interface. Not Stripe vs. Clerk
  Billing vs. other yet — the app must work end-to-end (auth, quota,
  admin) before that choice is made.
- **Admin config mechanism:** a real `/admin` web UI, not a config file or
  CLI tool — this is an ongoing operational need, not a one-time setup
  step.
- **Frontend stack:** Next.js (Clerk's best-supported integration), not
  the originally-planned deferred HTMX wizard. This supersedes
  ARCHITECTURE.md's "Phase 11" frontend plan for the parts that need
  auth/billing/admin; the pipeline's own review/wizard screens (spec §23,
  §24) still get built, just inside this Next.js app instead of a
  server-rendered one.
- **Pipeline hosting:** the FastAPI pipeline service runs on a separate
  long-running container host (Fly.io/Railway/Render-class), not Vercel
  serverless — OpenCV/Tesseract need a real OS-level binary, real
  execution time, and don't fit serverless constraints well.

## System topology

```
Browser
   |
Next.js (Vercel) ---- Clerk (auth: Google / email / OTP)
   |  owns: users mirror, subscriptions, usage counters, tier config,
   |        admin UI, audit log
   |  enforces quota BEFORE calling the pipeline
   |
   | HTTPS, internal service token
   v
FastAPI pipeline service (separate container host)
   owns: papers, questions, processing runs, artifacts — exactly what's
   already in DATA_MODEL.md / ARCHITECTURE.md. Knows nothing about
   users, tiers, or money. Still runnable headlessly via the CLI
   (spec §37) for local dev, skipping the quota check that only makes
   sense in the hosted product.
```

Two databases, one per service, to avoid two ORMs (Prisma + SQLAlchemy)
fighting over one schema and to keep a bug in quota logic from being able
to corrupt pipeline data or vice versa:

- **Next.js's Postgres** — SaaS-shaped data: users, subscriptions, usage
  counters, tier config, admin audit log. New in this spec.
- **FastAPI's database** — moves from SQLite to Postgres as part of this
  change. ARCHITECTURE.md already named "multi-user concurrent access" as
  the trigger for that move, and running as a real hosted service behind
  a product is exactly that trigger. Schema is unchanged from
  DATA_MODEL.md — this is a storage-engine swap, not a data-model change.

## Data model additions (Next.js's Postgres, via Prisma)

```
User
  id                  Clerk user ID, primary key
  email
  role                "user" | "admin"
  is_test_bypass_account   default false — see "Test bypass account" below
  created_at

Tier                                    <- admin-configurable
  id                  "guest" | "registered_free" | "subscribed_monthly"
                      | "subscribed_annual"
  name
  scans_per_period
  pdfs_per_period
  price_amount        nullable for guest/free
  currency
  billing_interval    "none" | "monthly" | "annual"
  is_active
  updated_at
  updated_by          -> User.id

Subscription
  id
  user_id             -> User.id
  tier_id             -> Tier.id            (subscribed_monthly | subscribed_annual)
  status              "active" | "canceled" | "past_due"
  started_at
  current_period_end
  external_subscription_id   nullable until a billing provider is chosen

UsageCounter
  id
  identity_type       "guest_ip" | "user"
  identity_key        salted SHA-256 hash of IP for guests, User.id for users
  period_start
  period_end          = period_start + 30 days (rolling)
  scans_used
  pdfs_used
  updated_at

AdminAuditLog
  id
  admin_user_id       -> User.id
  action               e.g. "tier.update"
  target               e.g. "subscribed_monthly.scans_per_period"
  old_value
  new_value
  created_at
```

`scans_used`/`pdfs_used` are tracked as two independent counters, matching
the original requirement (scans and PDF generations metered separately at
every tier). Tier limits are looked up live at request time: an admin
changing a limit, or a user's subscription changing tier, takes effect
immediately without resetting the counters already accumulated in the
current period.

`AdminAuditLog` exists because real money and quotas are at stake — a
mistaken admin edit should be traceable ("who changed this, from what, to
what, when") without needing a database backup to answer a support
question.

**Tier seed data:** the first migration inserts all four `Tier` rows with
`scans_per_period = 2` and `pdfs_per_period = 2` across the board — guest,
registered_free, subscribed_monthly, and subscribed_annual alike. This is
deliberately not differentiated at seed time; the admin sets each tier's
real numbers through the Tiers screen (Admin UI scope, below) once the
product is live. `price_amount` seeds `null` for guest/registered_free and
some placeholder for the paid tiers until pricing is decided.

## Test bypass account (PROD payment-gateway bypass for testing)

One designated account needs to exercise the subscribed tier in
production without going through a real payment. This is **not** a
separate authentication path — the account logs in exactly like any
other registered user (Clerk email/password, or whichever method is set
up for it). The bypass is narrower and lives entirely in the
subscription-status resolver:

- `User.is_test_bypass_account` (boolean, default `false`) — settable
  only by a direct database write (same operational tier as setting the
  first admin's `role`), never through any API endpoint or admin-UI
  form. There is no code path that can flip this flag from application
  code, so it cannot be self-elevated to by a compromised session.
- When the tier resolver (the "Determine current tier" step in Quota
  enforcement flow, below) sees `is_test_bypass_account = true`, it
  short-circuits: return a synthesized active `subscribed_annual` status
  (or whichever tier the test needs) **without** looking up a real
  `Subscription` row or calling `SubscriptionProvider`. No Stripe/Clerk
  Billing call happens for this account, ever.
- Every quota check against a bypass account writes an `AdminAuditLog`
  row (`action: "test_bypass.quota_check"`) — bypass usage in PROD stays
  traceable the same way an admin price edit is.
- Operational hygiene: use a non-obvious test email (not
  `test@test.com`), store the credential in a password manager rather
  than in code, docs, or chat, and treat flipping the flag on a second
  account as a real production change requiring the same care as any
  other direct DB edit.

This account is for exercising the subscribed-tier product experience
(quota limits, UI states) end-to-end in PROD without needing a live
payment method — not for load testing or for bypassing the scan/PDF
pipeline itself.

## Quota enforcement flow

Lives entirely in Next.js, in front of the pipeline call. The FastAPI
service never sees identity or tier — only an authorized request to
process a paper.

```
Request arrives (scan action or generate-PDF action)
   |
Determine identity
   - Clerk session present -> identity_type=user, identity_key=Clerk user ID
   - no session            -> identity_type=guest_ip,
                               identity_key=sha256(salt + request IP)
   |
Determine current tier
   - user: active Subscription row? -> subscribed_monthly / subscribed_annual
           else                     -> registered_free
   - guest_ip                       -> guest
   |
Get-or-create this period's UsageCounter row
   - no row, or now > period_end -> insert fresh row
     (period_start=now, period_end=now+30d, scans_used=0, pdfs_used=0)
   |
Compare counter against this tier's limits, inside one DB transaction
with a row lock (SELECT ... FOR UPDATE, or an atomic upsert-increment) —
this closes the race where two concurrent requests both read
"1 remaining" and both pass, over-granting by one.
   |
   +-- under limit --> increment the relevant counter, call FastAPI
   |
   +-- at/over limit --> reject: 402-style response with
                          { reason, tier, limit, used, upgrade_options }
```

**IP as guest identity is a soft, accepted limitation**, not a security
boundary. Shared/NAT IPs (offices, campuses, some mobile carriers) will
pool multiple real people under one guest quota; a VPN defeats it
entirely. Its only job is nudging a casual visitor toward registering —
building real anti-abuse tooling around a limit this soft would be
over-engineering for what it protects.

**FastAPI-side change:** pipeline endpoints require a shared internal
service token, attached by Next.js's backend, checked against
`core/secrets.py`. This is the only change to the pipeline service
itself from the Phase 1 design — never exposed to the browser.

### User-facing trigger: "Generate Sample Paper"

The wizard's device-camera/gallery upload step (spec §23 step 1) ends in
one button — **"Generate Sample Paper"** — rather than separate
"scan" and "generate" actions. One click runs the whole Workflow A chain
(ingest → clean → extract → generate → validate → render) and returns
both PDFs.

Because it's one user action spending two different quota buckets (scans,
counted per page uploaded — see the "Scan unit" decision above — and one
PDF-generation unit), both checks happen **up front, before any
processing starts**:

```
User taps "Generate Sample Paper" with N photos selected
   |
Check: does this identity have >= N scans remaining this period?
Check: does this identity have >= 1 PDF generation remaining this period?
   |
   +-- either check fails --> reject before calling FastAPI at all;
   |                          show the specific limit that blocked it
   |                          and the upgrade prompt
   |
   +-- both pass --> increment both counters, call FastAPI's full-chain
                      endpoint, stream pipeline progress (spec §38's
                      "[n/8] stage" observability) back to the button's
                      loading state, return question_paper.pdf +
                      answer_sheet.pdf on success
```

Checking both quotas before starting avoids the partial-failure case
where scanning succeeds (and consumes scan quota) but PDF generation then
fails on quota — the user would have paid for a scan and gotten nothing.
If the pipeline itself fails partway (a validation failure, a bad scan
per the image quality gate in PIPELINE.md), the spent quota units are
**not** refunded automatically for v1 — worth revisiting once there's
real failure-rate data to judge whether that's a support burden.

## Billing abstraction (provider deferred)

Same small-interface philosophy as `VisionProvider`/`OCRProvider` in
ARCHITECTURE.md:

```typescript
interface SubscriptionProvider {
  createCheckoutSession(userId: string, tierId: string): Promise<{ checkoutUrl: string }>
  handleWebhook(payload: unknown, signature: string): Promise<SubscriptionEvent>
  cancelSubscription(externalSubscriptionId: string): Promise<void>
}
```

`SubscriptionEvent` normalizes provider-specific webhook payloads into
`{ userId, tierId, status, currentPeriodEnd }` — the shape that writes/
updates `Subscription` rows. Until a concrete provider is chosen,
`Tier.price_amount`/`currency` stay fully admin-editable (they're display/
config values), but "Subscribe" is wired to a `NotConfiguredProvider`
stub that throws a clear, typed error — so auth, quota, and admin can be
built and tested end-to-end before a payment account exists.

## Admin UI scope (v1)

A `/admin` route in the same Next.js app, gated by `User.role ===
"admin"` (first admin set directly in the DB — no self-serve admin
signup). Three screens, deliberately not more:

- **Tiers** — edit `scans_per_period`, `pdfs_per_period`, `price_amount`,
  `currency`, `billing_interval`, `is_active` per tier. Every save writes
  an `AdminAuditLog` row.
- **Usage lookup** — search a user by email/ID, see their tier, current
  period's `scans_used`/`pdfs_used`, and period dates. Read-only support
  tool, not a bulk editor.
- **Audit log** — reverse-chronological `AdminAuditLog` listing.

## Testing approach

Quota logic (limit comparison, period rollover, concurrent-increment
race) is the part worth the most test investment: unit tests for the
pure comparison/rollover logic, and a test against a real Postgres
instance specifically for the row-lock/race behavior, since that's not
faithfully representable against SQLite or a mock. Webhook handling is
tested against recorded fixture payloads per eventual billing provider,
never against live calls. Admin UI screens get the same TDD treatment as
the rest of the codebase once implementation starts.

## Explicitly out of scope

- Team/org accounts (multiple users sharing one subscription)
- Proration, refunds, dunning/retry logic beyond what the chosen billing
  provider handles natively
- Localized pricing/currency beyond a single configured currency
- Self-serve admin invites (first admin is a manual DB edit)
- Abuse detection beyond the soft IP-based guest limit
