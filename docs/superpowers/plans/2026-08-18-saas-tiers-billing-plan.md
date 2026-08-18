# SaaS Tiers, Auth, and Billing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js SaaS shell (auth via Clerk, quota metering, billing
abstraction, admin UI) that sits in front of the FastAPI pipeline service —
guests, registered users, and subscribers get admin-configurable scan/PDF
quotas, enforced atomically before the pipeline is ever called.

**Architecture:** A new Next.js 15 (App Router, TypeScript) app at `web/`,
its own Postgres via Prisma, calling the FastAPI pipeline service over
HTTPS with a shared internal token. The FastAPI service itself (and its
own Postgres migration) is tracked separately in the main
`PROJECT_PLAN.md` / `TODO.md` — this plan only builds the Next.js side,
against a mocked pipeline-service HTTP call.

**Tech Stack:** Next.js 15 (App Router) + TypeScript, Prisma + Postgres,
Clerk (`@clerk/nextjs`) for auth, Vitest + React Testing Library for tests.

**Spec:** `docs/superpowers/specs/2026-08-18-saas-tiers-billing-design.md`

## Global Constraints

- Quota reset is **rolling 30 days per identity**, not calendar month —
  `period_end = period_start + 30 days`, computed fresh whenever the prior
  period has expired.
- **Scan unit** = one page/image uploaded. **PDF-generation unit** = one
  generated paper (question paper + answer sheet together), not two.
- **Over-quota is a hard block** — 402-style response
  `{ reason, tier, limit, used }`, no partial processing. Both the scan
  check and the PDF-generation check happen inside one DB transaction so a
  failure on either leaves **zero** counters incremented (all-or-nothing).
- Guest identity: `identity_type = "guest_ip"`, `identity_key =
  sha256(salt + request IP)`. User identity: `identity_type = "user"`,
  `identity_key = Clerk user ID`.
- **Tier seed defaults**: all four tiers (`guest`, `registered_free`,
  `subscribed_monthly`, `subscribed_annual`) seed with
  `scans_per_period = 2`, `pdfs_per_period = 2`. Admin-editable afterward
  — reseeding must never overwrite an admin's edited values.
- **Test bypass account**: `User.is_test_bypass_account` (boolean,
  default false, settable only by direct DB write — no API path sets it)
  short-circuits tier resolution to `subscribed_annual` without touching
  `Subscription` or the billing provider. Never call
  `SubscriptionProvider` for a bypass account.
- **Admin gate**: `User.role === "admin"`, first admin set by direct DB
  edit. Every admin write to `Tier` fields, and every quota check against
  a test-bypass account, writes an `AdminAuditLog` row.
- **Billing provider is deferred**: `SubscriptionProvider` interface only,
  backed by `NotConfiguredProvider`, which throws `BillingNotConfiguredError`.
- DB-touching tests run against a **real Postgres** reachable at
  `DATABASE_URL_TEST` (row-lock/concurrency behavior isn't representable
  against a mock or SQLite) — every DB-backed task assumes this is running
  and migrated (`npx prisma db push` against `DATABASE_URL_TEST`) before
  its tests execute.

---

## File Structure

```
web/
  package.json, tsconfig.json, next.config.ts, vitest.config.ts
  middleware.ts                        Clerk route protection (admin gate)
  prisma/
    schema.prisma
    seed.ts
  src/
    lib/
      identity.ts                      resolveIdentity()
      tier.ts                          resolveTier(), TEST_BYPASS_TIER
      quota.ts                         evaluateQuota() (pure)
      usageCounter.ts                  getOrCreateAndIncrement()
      quotaOrchestrator.ts             checkAndConsumeQuota()
      adminAuth.ts                     isAdminSession()
      auditLog.ts                      recordAuditLog()
      pipelineClient.ts                callPipelineService()
      prismaClient.ts                  shared Prisma client singleton
      billing/
        SubscriptionProvider.ts        interface + SubscriptionEvent + error
        NotConfiguredProvider.ts
    app/
      api/
        generate-sample-paper/route.ts
        admin/
          tiers/route.ts               GET (list)
          tiers/[id]/route.ts          PATCH (update one)
          usage/route.ts               GET (lookup)
          audit-log/route.ts           GET (list)
      admin/
        tiers/page.tsx
        usage/page.tsx
        audit-log/page.tsx
  tests/
    unit/        identity, quota, adminAuth, NotConfiguredProvider, pipelineClient
    integration/ seed, tier, usageCounter, quotaOrchestrator, auditLog,
                 tiersAdmin.route, usageAdmin.route, auditLogAdmin.route,
                 generateSamplePaper.route
    components/  TiersScreen, UsageLookupScreen, AuditLogScreen
```

---

### Task 1: Next.js + Prisma + Vitest scaffold

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`,
  `web/vitest.config.ts`, `web/.env.example`

**Interfaces:**
- Produces: a working `npm run test` (Vitest) and `npm run build` (Next.js)
  in `web/`, for every later task to build on.

This is scaffolding/configuration — no failing-test cycle applies (per
the TDD skill's own exception list). Steps are still checked off so
progress is trackable.

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "prepcraft-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "test": "vitest run",
    "prisma:generate": "prisma generate",
    "prisma:push": "prisma db push"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@clerk/nextjs": "^6.0.0",
    "@prisma/client": "^6.0.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "prisma": "^6.0.0",
    "vitest": "^2.1.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@testing-library/jest-dom": "^6.6.0"
  }
}
```

- [ ] **Step 2: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "ES2022"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src", "tests", "prisma", "next-env.d.ts"]
}
```

- [ ] **Step 3: Create `web/next.config.ts`**

```typescript
import type { NextConfig } from "next";

const config: NextConfig = {};

export default config;
```

- [ ] **Step 4: Create `web/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
  },
});
```

- [ ] **Step 5: Create `web/.env.example`**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/prepcraft
DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/prepcraft_test
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
GUEST_IP_SALT=
PIPELINE_SERVICE_URL=http://localhost:9000
PIPELINE_SERVICE_TOKEN=
```

- [ ] **Step 6: Install and verify**

Run: `cd web && npm install && npm run test`
Expected: Vitest runs with 0 test files found, exits 0 (no tests exist yet).

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/tsconfig.json web/next.config.ts web/vitest.config.ts web/.env.example
git commit -m "scaffold Next.js + Prisma + Vitest for the SaaS shell"
```

---

### Task 2: Prisma schema + tier seed script

**Files:**
- Create: `web/prisma/schema.prisma`, `web/prisma/seed.ts`
- Test: `web/tests/integration/seed.test.ts`

**Interfaces:**
- Produces: Prisma models `User`, `Tier`, `Subscription`, `UsageCounter`,
  `AdminAuditLog` (exact field names used by every later task);
  `seedTiers(client?: PrismaClient): Promise<void>`.

- [ ] **Step 1: Write `web/prisma/schema.prisma`**

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum UserRole {
  user
  admin
}

model User {
  id                  String          @id
  email               String          @unique
  role                UserRole        @default(user)
  isTestBypassAccount Boolean         @default(false) @map("is_test_bypass_account")
  createdAt           DateTime        @default(now()) @map("created_at")
  subscriptions       Subscription[]
  auditLogs           AdminAuditLog[] @relation("AuditLogAdmin")

  @@map("users")
}

enum TierId {
  guest
  registered_free
  subscribed_monthly
  subscribed_annual
}

enum BillingInterval {
  none
  monthly
  annual
}

model Tier {
  id              TierId          @id
  name            String
  scansPerPeriod  Int             @map("scans_per_period")
  pdfsPerPeriod   Int             @map("pdfs_per_period")
  priceAmount     Int?            @map("price_amount")
  currency        String?
  billingInterval BillingInterval @default(none) @map("billing_interval")
  isActive        Boolean         @default(true) @map("is_active")
  updatedAt       DateTime        @updatedAt @map("updated_at")
  updatedBy       String?         @map("updated_by")
  subscriptions   Subscription[]

  @@map("tiers")
}

enum SubscriptionStatus {
  active
  canceled
  past_due
}

model Subscription {
  id                     String             @id @default(cuid())
  userId                 String             @map("user_id")
  user                   User               @relation(fields: [userId], references: [id])
  tierId                 TierId             @map("tier_id")
  tier                   Tier               @relation(fields: [tierId], references: [id])
  status                 SubscriptionStatus
  startedAt              DateTime           @map("started_at")
  currentPeriodEnd       DateTime           @map("current_period_end")
  externalSubscriptionId String?            @map("external_subscription_id")

  @@index([userId, status])
  @@map("subscriptions")
}

enum IdentityType {
  guest_ip
  user
}

model UsageCounter {
  id           String       @id @default(cuid())
  identityType IdentityType @map("identity_type")
  identityKey  String       @map("identity_key")
  periodStart  DateTime     @map("period_start")
  periodEnd    DateTime     @map("period_end")
  scansUsed    Int          @default(0) @map("scans_used")
  pdfsUsed     Int          @default(0) @map("pdfs_used")
  updatedAt    DateTime     @updatedAt @map("updated_at")

  @@unique([identityType, identityKey, periodStart])
  @@map("usage_counters")
}

model AdminAuditLog {
  id          String   @id @default(cuid())
  adminUserId String   @map("admin_user_id")
  admin       User     @relation("AuditLogAdmin", fields: [adminUserId], references: [id])
  action      String
  target      String
  oldValue    String?  @map("old_value")
  newValue    String?  @map("new_value")
  createdAt   DateTime @default(now()) @map("created_at")

  @@map("admin_audit_log")
}
```

- [ ] **Step 2: Push the schema to the test database**

Run: `cd web && DATABASE_URL=$DATABASE_URL_TEST npx prisma db push`
Expected: tables created in the test Postgres.

- [ ] **Step 3: Write the failing test — `web/tests/integration/seed.test.ts`**

```typescript
import { PrismaClient } from "@prisma/client";
import { seedTiers } from "../../prisma/seed";

const prisma = new PrismaClient({
  datasources: { db: { url: process.env.DATABASE_URL_TEST } },
});

beforeEach(async () => {
  await prisma.tier.deleteMany();
});

afterAll(async () => {
  await prisma.$disconnect();
});

test("seedTiers creates all four tiers with scans=2 and pdfs=2", async () => {
  await seedTiers(prisma);

  const tiers = await prisma.tier.findMany({ orderBy: { id: "asc" } });

  expect(tiers).toHaveLength(4);
  for (const tier of tiers) {
    expect(tier.scansPerPeriod).toBe(2);
    expect(tier.pdfsPerPeriod).toBe(2);
  }
});

test("seedTiers is idempotent and never overwrites an admin's edited values", async () => {
  await seedTiers(prisma);
  await prisma.tier.update({ where: { id: "guest" }, data: { scansPerPeriod: 5 } });

  await seedTiers(prisma);

  const guest = await prisma.tier.findUniqueOrThrow({ where: { id: "guest" } });
  expect(guest.scansPerPeriod).toBe(5);
  expect(await prisma.tier.count()).toBe(4);
});
```

- [ ] **Step 4: Verify RED**

Run: `cd web && npx vitest run tests/integration/seed.test.ts`
Expected: FAIL — `Cannot find module '../../prisma/seed'`

- [ ] **Step 5: Write `web/prisma/seed.ts`**

```typescript
import { PrismaClient, type TierId } from "@prisma/client";

const prisma = new PrismaClient();

const DEFAULT_TIERS: Array<{ id: TierId; name: string }> = [
  { id: "guest", name: "Guest" },
  { id: "registered_free", name: "Registered (Free)" },
  { id: "subscribed_monthly", name: "Subscribed (Monthly)" },
  { id: "subscribed_annual", name: "Subscribed (Annual)" },
];

export async function seedTiers(client: PrismaClient = prisma): Promise<void> {
  for (const tier of DEFAULT_TIERS) {
    await client.tier.upsert({
      where: { id: tier.id },
      update: {},
      create: {
        id: tier.id,
        name: tier.name,
        scansPerPeriod: 2,
        pdfsPerPeriod: 2,
      },
    });
  }
}

if (require.main === module) {
  seedTiers().finally(() => prisma.$disconnect());
}
```

- [ ] **Step 6: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/seed.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add web/prisma/schema.prisma web/prisma/seed.ts web/tests/integration/seed.test.ts
git commit -m "add Prisma schema and idempotent tier seed script"
```

---

### Task 3: Identity resolution (pure)

**Files:**
- Create: `web/src/lib/identity.ts`
- Test: `web/tests/unit/identity.test.ts`

**Interfaces:**
- Produces: `resolveIdentity(clerkUserId: string | null, ipAddress: string, ipSalt: string): Identity`
  where `Identity = { type: "user"; key: string } | { type: "guest_ip"; key: string }`.

- [ ] **Step 1: Write the failing test**

```typescript
import { resolveIdentity } from "../../src/lib/identity";

test("returns a user identity keyed by the Clerk user ID when signed in", () => {
  const identity = resolveIdentity("user_abc123", "203.0.113.5", "salt");
  expect(identity).toEqual({ type: "user", key: "user_abc123" });
});

test("returns a guest_ip identity keyed by a salted hash of the IP when signed out", () => {
  const identity = resolveIdentity(null, "203.0.113.5", "salt");
  expect(identity.type).toBe("guest_ip");
  expect(identity.key).toMatch(/^[0-9a-f]{64}$/);
});

test("the same IP and salt always hash to the same guest key", () => {
  const a = resolveIdentity(null, "203.0.113.5", "salt");
  const b = resolveIdentity(null, "203.0.113.5", "salt");
  expect(a.key).toBe(b.key);
});

test("different IPs hash to different guest keys", () => {
  const a = resolveIdentity(null, "203.0.113.5", "salt");
  const b = resolveIdentity(null, "203.0.113.6", "salt");
  expect(a.key).not.toBe(b.key);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/unit/identity.test.ts`
Expected: FAIL — `Cannot find module '../../src/lib/identity'`

- [ ] **Step 3: Write `web/src/lib/identity.ts`**

```typescript
import { createHash } from "node:crypto";

export type Identity =
  | { type: "user"; key: string }
  | { type: "guest_ip"; key: string };

export function resolveIdentity(
  clerkUserId: string | null,
  ipAddress: string,
  ipSalt: string
): Identity {
  if (clerkUserId) {
    return { type: "user", key: clerkUserId };
  }
  const hash = createHash("sha256").update(ipSalt + ipAddress).digest("hex");
  return { type: "guest_ip", key: hash };
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/unit/identity.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/identity.ts web/tests/unit/identity.test.ts
git commit -m "add pure identity resolution (user vs. hashed guest IP)"
```

---

### Task 4: Tier resolution, including test-bypass short-circuit

**Files:**
- Create: `web/src/lib/tier.ts`
- Test: `web/tests/integration/tier.test.ts`

**Interfaces:**
- Consumes: `Identity` from Task 3; `User`, `Subscription`, `TierId` from
  Task 2's Prisma schema.
- Produces: `TierResolution = { tierId: TierId; isBypass: boolean }`;
  `resolveTier(identity: Identity, prisma: PrismaClient): Promise<TierResolution>`;
  `TEST_BYPASS_TIER: TierId`. `isBypass` is what lets Task 7 know to write
  the audit log the spec requires for every bypass-account quota check —
  without it, a real subscriber who happens to land on
  `subscribed_annual` would be indistinguishable from a bypass account.

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";
import { resolveTier, TEST_BYPASS_TIER } from "../../src/lib/tier";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.subscription.deleteMany();
  await prisma.user.deleteMany();
});
afterAll(() => prisma.$disconnect());

test("guest_ip identity always resolves to the guest tier", async () => {
  const result = await resolveTier({ type: "guest_ip", key: "hash123" }, prisma);
  expect(result).toEqual({ tierId: "guest", isBypass: false });
});

test("a registered user with no subscription resolves to registered_free", async () => {
  await prisma.user.create({ data: { id: "user_1", email: "a@example.com" } });
  const result = await resolveTier({ type: "user", key: "user_1" }, prisma);
  expect(result).toEqual({ tierId: "registered_free", isBypass: false });
});

test("a user with an active subscription resolves to that subscription's tier", async () => {
  await prisma.user.create({ data: { id: "user_2", email: "b@example.com" } });
  await prisma.subscription.create({
    data: {
      userId: "user_2",
      tierId: "subscribed_monthly",
      status: "active",
      startedAt: new Date(),
      currentPeriodEnd: new Date(Date.now() + 86_400_000),
    },
  });
  const result = await resolveTier({ type: "user", key: "user_2" }, prisma);
  expect(result).toEqual({ tierId: "subscribed_monthly", isBypass: false });
});

test("a test-bypass account resolves to the bypass tier and flags isBypass, without needing a Subscription row", async () => {
  await prisma.user.create({
    data: { id: "user_3", email: "bypass@example.com", isTestBypassAccount: true },
  });
  const result = await resolveTier({ type: "user", key: "user_3" }, prisma);
  expect(result).toEqual({ tierId: TEST_BYPASS_TIER, isBypass: true });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/tier.test.ts`
Expected: FAIL — `Cannot find module '../../src/lib/tier'`

- [ ] **Step 3: Write `web/src/lib/tier.ts`**

```typescript
import type { PrismaClient, TierId } from "@prisma/client";
import type { Identity } from "./identity";

export const TEST_BYPASS_TIER: TierId = "subscribed_annual";

export interface TierResolution {
  tierId: TierId;
  isBypass: boolean;
}

export async function resolveTier(identity: Identity, prisma: PrismaClient): Promise<TierResolution> {
  if (identity.type === "guest_ip") {
    return { tierId: "guest", isBypass: false };
  }

  const user = await prisma.user.findUnique({ where: { id: identity.key } });
  if (user?.isTestBypassAccount) {
    return { tierId: TEST_BYPASS_TIER, isBypass: true };
  }

  const activeSubscription = await prisma.subscription.findFirst({
    where: { userId: identity.key, status: "active" },
    orderBy: { currentPeriodEnd: "desc" },
  });

  return { tierId: activeSubscription?.tierId ?? "registered_free", isBypass: false };
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/tier.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/tier.ts web/tests/integration/tier.test.ts
git commit -m "add tier resolution incl. test-bypass-account short-circuit"
```

---

### Task 5: Quota evaluation (pure)

**Files:**
- Create: `web/src/lib/quota.ts`
- Test: `web/tests/unit/quota.test.ts`

**Interfaces:**
- Produces: `UsageCounterState`, `QuotaEvaluation`,
  `evaluateQuota(counter: UsageCounterState | null, now: Date, limit: number, requested: number, metric: "scansUsed" | "pdfsUsed"): QuotaEvaluation`.

- [ ] **Step 1: Write the failing test**

```typescript
import { evaluateQuota } from "../../src/lib/quota";

const now = new Date("2026-08-18T00:00:00Z");

test("no existing counter starts a fresh 30-day period and allows a request within the limit", () => {
  const result = evaluateQuota(null, now, 2, 1, "scansUsed");
  expect(result.allowed).toBe(true);
  expect(result.needsNewPeriod).toBe(true);
  expect(result.periodStart).toEqual(now);
  expect(result.periodEnd).toEqual(new Date("2026-09-17T00:00:00Z"));
});

test("a request that would exceed the limit within an active period is rejected", () => {
  const counter = {
    periodStart: new Date("2026-08-01T00:00:00Z"),
    periodEnd: new Date("2026-08-31T00:00:00Z"),
    scansUsed: 2,
    pdfsUsed: 0,
  };
  const result = evaluateQuota(counter, now, 2, 1, "scansUsed");
  expect(result.allowed).toBe(false);
  expect(result.needsNewPeriod).toBe(false);
});

test("a request exactly at the remaining headroom is allowed", () => {
  const counter = {
    periodStart: new Date("2026-08-01T00:00:00Z"),
    periodEnd: new Date("2026-08-31T00:00:00Z"),
    scansUsed: 1,
    pdfsUsed: 0,
  };
  const result = evaluateQuota(counter, now, 2, 1, "scansUsed");
  expect(result.allowed).toBe(true);
});

test("a counter whose period already ended resets to a fresh period regardless of prior usage", () => {
  const counter = {
    periodStart: new Date("2026-06-01T00:00:00Z"),
    periodEnd: new Date("2026-07-01T00:00:00Z"),
    scansUsed: 2,
    pdfsUsed: 0,
  };
  const result = evaluateQuota(counter, now, 2, 2, "scansUsed");
  expect(result.allowed).toBe(true);
  expect(result.needsNewPeriod).toBe(true);
});

test("a multi-unit request (e.g. a multi-page scan) is checked against the full requested amount", () => {
  const result = evaluateQuota(null, now, 2, 3, "scansUsed");
  expect(result.allowed).toBe(false);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/unit/quota.test.ts`
Expected: FAIL — `Cannot find module '../../src/lib/quota'`

- [ ] **Step 3: Write `web/src/lib/quota.ts`**

```typescript
export interface UsageCounterState {
  periodStart: Date;
  periodEnd: Date;
  scansUsed: number;
  pdfsUsed: number;
}

export interface QuotaEvaluation {
  allowed: boolean;
  needsNewPeriod: boolean;
  periodStart: Date;
  periodEnd: Date;
}

const PERIOD_LENGTH_MS = 30 * 24 * 60 * 60 * 1000;

export function evaluateQuota(
  counter: UsageCounterState | null,
  now: Date,
  limit: number,
  requested: number,
  metric: "scansUsed" | "pdfsUsed"
): QuotaEvaluation {
  const needsNewPeriod = counter === null || now.getTime() >= counter.periodEnd.getTime();

  const periodStart = needsNewPeriod ? now : counter!.periodStart;
  const periodEnd = needsNewPeriod
    ? new Date(now.getTime() + PERIOD_LENGTH_MS)
    : counter!.periodEnd;
  const used = needsNewPeriod ? 0 : counter![metric];

  return {
    allowed: used + requested <= limit,
    needsNewPeriod,
    periodStart,
    periodEnd,
  };
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/unit/quota.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/quota.ts web/tests/unit/quota.test.ts
git commit -m "add pure quota limit/rollover evaluation"
```

---

### Task 6: Atomic UsageCounter get-or-create-and-increment

**Files:**
- Create: `web/src/lib/usageCounter.ts`
- Test: `web/tests/integration/usageCounter.test.ts`

**Interfaces:**
- Consumes: `evaluateQuota`, `UsageCounterState` from Task 5;
  `UsageCounter`, `IdentityType` from Task 2.
- Produces: `ConsumeResult = { allowed: boolean; used: number; limit: number }`;
  `getOrCreateAndIncrement(prisma, identityType, identityKey, metric, requested, limit, now?): Promise<ConsumeResult>`.

Known, accepted limitation (documented, not silently ignored): the very
first request ever made for a given identity+period is protected by the
table's unique constraint, not by `FOR UPDATE` (which finds no row to
lock yet) — a true simultaneous *first* request for a brand-new period
could 500 on the unique-constraint violation rather than being cleanly
rejected. This is rare (once per identity per 30-day period) and is a
named follow-up, not solved in this task.

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";
import { getOrCreateAndIncrement } from "../../src/lib/usageCounter";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
});
afterAll(() => prisma.$disconnect());

test("increments scansUsed and allows a request within the limit", async () => {
  const result = await getOrCreateAndIncrement(prisma, "user", "user_1", "scansUsed", 1, 2);
  expect(result).toEqual({ allowed: true, used: 1, limit: 2 });
});

test("rejects a request that would exceed the limit", async () => {
  await getOrCreateAndIncrement(prisma, "user", "user_2", "scansUsed", 2, 2);
  const result = await getOrCreateAndIncrement(prisma, "user", "user_2", "scansUsed", 1, 2);
  expect(result.allowed).toBe(false);
});

test("two concurrent increments against a counter with 1 unit of headroom: exactly one succeeds", async () => {
  await getOrCreateAndIncrement(prisma, "user", "user_3", "scansUsed", 1, 2); // 1 used, 1 remaining

  const [a, b] = await Promise.all([
    getOrCreateAndIncrement(prisma, "user", "user_3", "scansUsed", 1, 2),
    getOrCreateAndIncrement(prisma, "user", "user_3", "scansUsed", 1, 2),
  ]);

  const allowedCount = [a, b].filter((r) => r.allowed).length;
  expect(allowedCount).toBe(1);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/usageCounter.test.ts`
Expected: FAIL — `Cannot find module '../../src/lib/usageCounter'`

- [ ] **Step 3: Write `web/src/lib/usageCounter.ts`**

```typescript
import type { PrismaClient, IdentityType } from "@prisma/client";
import { evaluateQuota, type UsageCounterState } from "./quota";

export interface ConsumeResult {
  allowed: boolean;
  used: number;
  limit: number;
}

export async function getOrCreateAndIncrement(
  prisma: PrismaClient,
  identityType: IdentityType,
  identityKey: string,
  metric: "scansUsed" | "pdfsUsed",
  requested: number,
  limit: number,
  now: Date = new Date()
): Promise<ConsumeResult> {
  return prisma.$transaction(async (tx) => {
    const rows = await tx.$queryRaw<UsageCounterState[]>`
      SELECT period_start as "periodStart", period_end as "periodEnd",
             scans_used as "scansUsed", pdfs_used as "pdfsUsed"
      FROM usage_counters
      WHERE identity_type = ${identityType} AND identity_key = ${identityKey}
      ORDER BY period_end DESC
      LIMIT 1
      FOR UPDATE
    `;
    const existing = rows[0] ?? null;

    const evaluation = evaluateQuota(existing, now, limit, requested, metric);

    if (!evaluation.allowed) {
      return { allowed: false, used: existing?.[metric] ?? 0, limit };
    }

    if (evaluation.needsNewPeriod) {
      await tx.usageCounter.create({
        data: {
          identityType,
          identityKey,
          periodStart: evaluation.periodStart,
          periodEnd: evaluation.periodEnd,
          scansUsed: metric === "scansUsed" ? requested : 0,
          pdfsUsed: metric === "pdfsUsed" ? requested : 0,
        },
      });
      return { allowed: true, used: requested, limit };
    }

    const updated = await tx.usageCounter.update({
      where: {
        identityType_identityKey_periodStart: {
          identityType,
          identityKey,
          periodStart: evaluation.periodStart,
        },
      },
      data: { [metric]: { increment: requested } },
    });

    return { allowed: true, used: updated[metric], limit };
  });
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/usageCounter.test.ts`
Expected: PASS (3 tests) — the concurrency test is the one that actually
proves the row lock works; if it's flaky, the lock isn't holding.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/usageCounter.ts web/tests/integration/usageCounter.test.ts
git commit -m "add race-safe atomic usage counter increment"
```

---

### Task 7: Quota orchestrator (all-or-nothing across scans + PDFs)

**Files:**
- Create: `web/src/lib/quotaOrchestrator.ts`
- Test: `web/tests/integration/quotaOrchestrator.test.ts`

**Interfaces:**
- Consumes: `resolveIdentity` (Task 3), `resolveTier` / `TierResolution`
  (Task 4), `getOrCreateAndIncrement` (Task 6), `recordAuditLog`
  (Task 10 — pulled forward here since the bypass-audit requirement lives
  in this function), `seedTiers` (Task 2, test only).
- Produces: `QuotaCheckInput`, `QuotaCheckResult`,
  `checkAndConsumeQuota(prisma, input): Promise<QuotaCheckResult>`.

Note this task now depends on Task 10's `recordAuditLog` — do Task 10
before this one, ahead of its position in the file (or bring
`recordAuditLog`'s implementation forward; it's a 12-line pure DB write
with no dependency of its own on anything after Task 2).

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";
import { checkAndConsumeQuota } from "../../src/lib/quotaOrchestrator";
import { seedTiers } from "../../prisma/seed";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
  await prisma.adminAuditLog.deleteMany(); // must clear before user.deleteMany() (FK)
  await prisma.subscription.deleteMany();
  await prisma.user.deleteMany();
  await prisma.tier.deleteMany();
  await seedTiers(prisma);
});
afterAll(() => prisma.$disconnect());

test("a guest within both limits is allowed", async () => {
  const result = await checkAndConsumeQuota(prisma, {
    clerkUserId: null,
    ipAddress: "203.0.113.5",
    ipSalt: "salt",
    scanCount: 1,
  });
  expect(result.allowed).toBe(true);
});

test("a guest who already used both scan units for the period is rejected on the scan check", async () => {
  const input = { clerkUserId: null, ipAddress: "203.0.113.9", ipSalt: "salt", scanCount: 2 };
  await checkAndConsumeQuota(prisma, input); // consumes guest's 2/2 scans and pdfs

  const result = await checkAndConsumeQuota(prisma, { ...input, scanCount: 1 });
  expect(result).toMatchObject({ allowed: false, reason: "scans" });
});

test("rejecting on the scan check never touches the pdf counter (all-or-nothing)", async () => {
  const input = { clerkUserId: null, ipAddress: "203.0.113.30", ipSalt: "salt", scanCount: 3 }; // exceeds guest's 2-scan limit immediately

  const result = await checkAndConsumeQuota(prisma, input);

  expect(result).toMatchObject({ allowed: false, reason: "scans" });
  const counter = await prisma.usageCounter.findFirst({ where: { identityType: "guest_ip" } });
  expect(counter).toBeNull(); // transaction rolled back — no counter row was ever committed
});

test("a test-bypass account's quota check writes an AdminAuditLog row, regardless of outcome", async () => {
  await prisma.user.create({
    data: { id: "bypass_user", email: "bypass@example.com", isTestBypassAccount: true },
  });

  await checkAndConsumeQuota(prisma, {
    clerkUserId: "bypass_user",
    ipAddress: "203.0.113.50",
    ipSalt: "salt",
    scanCount: 1,
  });

  const logs = await prisma.adminAuditLog.findMany({ where: { adminUserId: "bypass_user" } });
  expect(logs).toHaveLength(1);
  expect(logs[0].action).toBe("test_bypass.quota_check");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/quotaOrchestrator.test.ts`
Expected: FAIL — `Cannot find module '../../src/lib/quotaOrchestrator'`

- [ ] **Step 3: Write `web/src/lib/quotaOrchestrator.ts`**

```typescript
import type { PrismaClient } from "@prisma/client";
import { resolveIdentity, type Identity } from "./identity";
import { resolveTier } from "./tier";
import { getOrCreateAndIncrement } from "./usageCounter";
import { recordAuditLog } from "./auditLog";

export interface QuotaCheckInput {
  clerkUserId: string | null;
  ipAddress: string;
  ipSalt: string;
  scanCount: number;
}

export type QuotaCheckResult =
  | { allowed: true; identity: Identity }
  | { allowed: false; reason: "scans" | "pdfs"; tier: string; limit: number; used: number };

class QuotaRollback extends Error {
  constructor(public result: Extract<QuotaCheckResult, { allowed: false }>) {
    super("quota check failed — transaction rolled back");
  }
}

export async function checkAndConsumeQuota(
  prisma: PrismaClient,
  input: QuotaCheckInput
): Promise<QuotaCheckResult> {
  const identity = resolveIdentity(input.clerkUserId, input.ipAddress, input.ipSalt);
  const { tierId, isBypass } = await resolveTier(identity, prisma);
  const tier = await prisma.tier.findUniqueOrThrow({ where: { id: tierId } });

  // Runs the quota check in its own transaction so a rejection rolls back
  // BOTH counters (all-or-nothing). The audit-log write below deliberately
  // happens outside this transaction, using the top-level `prisma` client
  // (not `tx`) — a bypass account's usage must stay traceable even when
  // the quota check itself is rejected and rolled back.
  const result = await prisma
    .$transaction(async (tx) => {
      const scanResult = await getOrCreateAndIncrement(
        tx as PrismaClient,
        identity.type,
        identity.key,
        "scansUsed",
        input.scanCount,
        tier.scansPerPeriod
      );
      if (!scanResult.allowed) {
        throw new QuotaRollback({
          allowed: false,
          reason: "scans",
          tier: tierId,
          limit: scanResult.limit,
          used: scanResult.used,
        });
      }

      const pdfResult = await getOrCreateAndIncrement(
        tx as PrismaClient,
        identity.type,
        identity.key,
        "pdfsUsed",
        1,
        tier.pdfsPerPeriod
      );
      if (!pdfResult.allowed) {
        throw new QuotaRollback({
          allowed: false,
          reason: "pdfs",
          tier: tierId,
          limit: pdfResult.limit,
          used: pdfResult.used,
        });
      }

      return { allowed: true, identity } as const;
    })
    .catch((err) => {
      if (err instanceof QuotaRollback) return err.result;
      throw err;
    });

  if (isBypass) {
    await recordAuditLog(prisma, {
      adminUserId: identity.key,
      action: "test_bypass.quota_check",
      target: identity.key,
      newValue: result.allowed ? "allowed" : `rejected:${result.reason}`,
    });
  }

  return result;
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/quotaOrchestrator.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/quotaOrchestrator.ts web/tests/integration/quotaOrchestrator.test.ts
git commit -m "add all-or-nothing quota orchestrator for scans + PDF generation"
```

---

### Task 8: Admin auth predicate + Clerk middleware

**Files:**
- Create: `web/src/lib/adminAuth.ts`, `web/middleware.ts`
- Test: `web/tests/unit/adminAuth.test.ts`

**Interfaces:**
- Produces: `isAdminSession(claims: { role?: string } | null): boolean`,
  used by both `middleware.ts` and every admin API route.

- [ ] **Step 1: Write the failing test**

```typescript
import { isAdminSession } from "../../src/lib/adminAuth";

test("returns true when the session claims carry role admin", () => {
  expect(isAdminSession({ role: "admin" })).toBe(true);
});

test("returns false for a regular user role", () => {
  expect(isAdminSession({ role: "user" })).toBe(false);
});

test("returns false when there are no session claims (signed out)", () => {
  expect(isAdminSession(null)).toBe(false);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/unit/adminAuth.test.ts`
Expected: FAIL — `Cannot find module '../../src/lib/adminAuth'`

- [ ] **Step 3: Write `web/src/lib/adminAuth.ts`**

```typescript
export interface SessionClaims {
  role?: string;
}

export function isAdminSession(claims: SessionClaims | null): boolean {
  return claims?.role === "admin";
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/unit/adminAuth.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Write `web/middleware.ts`** (thin adapter over the tested
      predicate — Next.js middleware itself isn't unit-testable without a
      full dev server, so it stays as small as possible)

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { isAdminSession } from "./src/lib/adminAuth";

const isAdminRoute = createRouteMatcher(["/admin(.*)", "/api/admin(.*)"]);

export default clerkMiddleware((auth, req) => {
  if (isAdminRoute(req)) {
    const { sessionClaims } = auth();
    if (!isAdminSession(sessionClaims as { role?: string } | null)) {
      return NextResponse.redirect(new URL("/", req.url));
    }
  }
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"],
};
```

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/adminAuth.ts web/middleware.ts web/tests/unit/adminAuth.test.ts
git commit -m "add admin session predicate and Clerk route-gating middleware"
```

---

### Task 9: Billing abstraction + NotConfiguredProvider

**Files:**
- Create: `web/src/lib/billing/SubscriptionProvider.ts`,
  `web/src/lib/billing/NotConfiguredProvider.ts`
- Test: `web/tests/unit/NotConfiguredProvider.test.ts`

**Interfaces:**
- Produces: `SubscriptionProvider` interface, `SubscriptionEvent`,
  `BillingNotConfiguredError`, `NotConfiguredProvider` (implements
  `SubscriptionProvider`).

- [ ] **Step 1: Write the failing test**

```typescript
import { NotConfiguredProvider } from "../../src/lib/billing/NotConfiguredProvider";
import { BillingNotConfiguredError } from "../../src/lib/billing/SubscriptionProvider";

test("createCheckoutSession throws BillingNotConfiguredError", async () => {
  const provider = new NotConfiguredProvider();
  await expect(provider.createCheckoutSession("user_1", "subscribed_monthly")).rejects.toThrow(
    BillingNotConfiguredError
  );
});

test("cancelSubscription throws BillingNotConfiguredError", async () => {
  const provider = new NotConfiguredProvider();
  await expect(provider.cancelSubscription("sub_123")).rejects.toThrow(BillingNotConfiguredError);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/unit/NotConfiguredProvider.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/lib/billing/SubscriptionProvider.ts`**

```typescript
export interface SubscriptionEvent {
  userId: string;
  tierId: string;
  status: "active" | "canceled" | "past_due";
  currentPeriodEnd: Date;
}

export interface SubscriptionProvider {
  createCheckoutSession(userId: string, tierId: string): Promise<{ checkoutUrl: string }>;
  handleWebhook(payload: unknown, signature: string): Promise<SubscriptionEvent>;
  cancelSubscription(externalSubscriptionId: string): Promise<void>;
}

export class BillingNotConfiguredError extends Error {
  constructor() {
    super("No billing provider is configured yet — subscriptions cannot be created.");
    this.name = "BillingNotConfiguredError";
  }
}
```

- [ ] **Step 4: Write `web/src/lib/billing/NotConfiguredProvider.ts`**

```typescript
import { BillingNotConfiguredError, type SubscriptionProvider } from "./SubscriptionProvider";

export class NotConfiguredProvider implements SubscriptionProvider {
  async createCheckoutSession(): Promise<{ checkoutUrl: string }> {
    throw new BillingNotConfiguredError();
  }
  async handleWebhook(): Promise<never> {
    throw new BillingNotConfiguredError();
  }
  async cancelSubscription(): Promise<void> {
    throw new BillingNotConfiguredError();
  }
}
```

- [ ] **Step 5: Verify GREEN**

Run: `cd web && npx vitest run tests/unit/NotConfiguredProvider.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/billing/ web/tests/unit/NotConfiguredProvider.test.ts
git commit -m "add SubscriptionProvider interface and NotConfiguredProvider stub"
```

---

### Task 10: Audit log helper

**Files:**
- Create: `web/src/lib/auditLog.ts`
- Test: `web/tests/integration/auditLog.test.ts`

**Interfaces:**
- Consumes: `AdminAuditLog` model from Task 2.
- Produces: `AuditLogEntry`, `recordAuditLog(prisma, entry): Promise<void>`.

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";
import { recordAuditLog } from "../../src/lib/auditLog";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.adminAuditLog.deleteMany();
  await prisma.user.deleteMany();
  await prisma.user.create({ data: { id: "admin_1", email: "admin@example.com", role: "admin" } });
});
afterAll(() => prisma.$disconnect());

test("writes an audit log row with the given fields", async () => {
  await recordAuditLog(prisma, {
    adminUserId: "admin_1",
    action: "tier.update",
    target: "subscribed_monthly.scans_per_period",
    oldValue: "2",
    newValue: "30",
  });

  const rows = await prisma.adminAuditLog.findMany();
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({
    adminUserId: "admin_1",
    action: "tier.update",
    target: "subscribed_monthly.scans_per_period",
    oldValue: "2",
    newValue: "30",
  });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/auditLog.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/lib/auditLog.ts`**

```typescript
import type { PrismaClient } from "@prisma/client";

export interface AuditLogEntry {
  adminUserId: string;
  action: string;
  target: string;
  oldValue?: string;
  newValue?: string;
}

export async function recordAuditLog(prisma: PrismaClient, entry: AuditLogEntry): Promise<void> {
  await prisma.adminAuditLog.create({
    data: {
      adminUserId: entry.adminUserId,
      action: entry.action,
      target: entry.target,
      oldValue: entry.oldValue ?? null,
      newValue: entry.newValue ?? null,
    },
  });
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/auditLog.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/auditLog.ts web/tests/integration/auditLog.test.ts
git commit -m "add admin audit log write helper"
```

---

### Task 11: Pipeline service client

**Files:**
- Create: `web/src/lib/pipelineClient.ts`
- Test: `web/tests/unit/pipelineClient.test.ts`

**Interfaces:**
- Produces: `PipelineResult = { questionPaperUrl: string; answerSheetUrl: string }`,
  `callPipelineService(imageUrls, serviceUrl, serviceToken, fetchImpl?): Promise<PipelineResult>`.

This is the one place a mock is the right call (per the TDD skill: "mocks
only if unavoidable") — the FastAPI pipeline service doesn't exist yet in
this plan's scope (it's tracked in `PROJECT_PLAN.md`/`TODO.md`), so
`fetch` is injected and faked here.

- [ ] **Step 1: Write the failing test**

```typescript
import { callPipelineService } from "../../src/lib/pipelineClient";

test("posts image URLs to the pipeline service with the bearer token and returns the result", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ questionPaperUrl: "https://x/qp.pdf", answerSheetUrl: "https://x/as.pdf" }),
  });

  const result = await callPipelineService(
    ["https://x/img1.jpg"],
    "https://pipeline.internal",
    "secret-token",
    fetchMock as unknown as typeof fetch
  );

  expect(result).toEqual({ questionPaperUrl: "https://x/qp.pdf", answerSheetUrl: "https://x/as.pdf" });
  expect(fetchMock).toHaveBeenCalledWith(
    "https://pipeline.internal/generate",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer secret-token" }),
    })
  );
});

test("throws when the pipeline service responds with a non-OK status", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 });
  await expect(
    callPipelineService(["x"], "https://pipeline.internal", "t", fetchMock as unknown as typeof fetch)
  ).rejects.toThrow("500");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/unit/pipelineClient.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/lib/pipelineClient.ts`**

```typescript
export interface PipelineResult {
  questionPaperUrl: string;
  answerSheetUrl: string;
}

export async function callPipelineService(
  imageUrls: string[],
  serviceUrl: string,
  serviceToken: string,
  fetchImpl: typeof fetch = fetch
): Promise<PipelineResult> {
  const res = await fetchImpl(`${serviceUrl}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${serviceToken}`,
    },
    body: JSON.stringify({ image_urls: imageUrls }),
  });

  if (!res.ok) {
    throw new Error(`pipeline service returned ${res.status}`);
  }

  return res.json();
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/unit/pipelineClient.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/pipelineClient.ts web/tests/unit/pipelineClient.test.ts
git commit -m "add pipeline service HTTP client"
```

---

### Task 12: API route — POST /api/generate-sample-paper

**Files:**
- Create: `web/src/lib/prismaClient.ts`, `web/src/app/api/generate-sample-paper/route.ts`
- Test: `web/tests/integration/generateSamplePaper.route.test.ts`

**Interfaces:**
- Consumes: `checkAndConsumeQuota` (Task 7), `callPipelineService` (Task 11).
- Produces: `POST` handler returning `200` with `PipelineResult` or `402`
  with `{ reason, tier, limit, used }`.

- [ ] **Step 1: Write `web/src/lib/prismaClient.ts`** (shared singleton,
      standard Next.js dev-hot-reload pattern — config, not tested directly)

```typescript
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
```

- [ ] **Step 2: Write the failing test — `web/tests/integration/generateSamplePaper.route.test.ts`**

```typescript
import { PrismaClient } from "@prisma/client";
import { seedTiers } from "../../prisma/seed";

vi.mock("@clerk/nextjs/server", () => ({
  auth: () => ({ userId: null }),
}));

vi.mock("../../src/lib/pipelineClient", () => ({
  callPipelineService: vi.fn().mockResolvedValue({
    questionPaperUrl: "https://x/qp.pdf",
    answerSheetUrl: "https://x/as.pdf",
  }),
}));

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
  await prisma.tier.deleteMany();
  await seedTiers(prisma);
  vi.stubEnv("GUEST_IP_SALT", "salt");
  vi.stubEnv("PIPELINE_SERVICE_URL", "https://pipeline.internal");
  vi.stubEnv("PIPELINE_SERVICE_TOKEN", "token");
});
afterAll(() => prisma.$disconnect());

test("a guest within quota gets both PDF URLs back", async () => {
  const { POST } = await import("../../src/app/api/generate-sample-paper/route");
  const req = new Request("https://app.test/api/generate-sample-paper", {
    method: "POST",
    headers: { "x-forwarded-for": "203.0.113.5" },
    body: JSON.stringify({ imageUrls: ["https://x/img1.jpg"] }),
  });

  const res = await POST(req as any);
  const body = await res.json();

  expect(res.status).toBe(200);
  expect(body).toEqual({ questionPaperUrl: "https://x/qp.pdf", answerSheetUrl: "https://x/as.pdf" });
});

test("a guest over quota gets a 402 with the reason, never calling the pipeline", async () => {
  const { POST } = await import("../../src/app/api/generate-sample-paper/route");
  const { callPipelineService } = await import("../../src/lib/pipelineClient");

  const makeReq = () =>
    new Request("https://app.test/api/generate-sample-paper", {
      method: "POST",
      headers: { "x-forwarded-for": "203.0.113.9" },
      body: JSON.stringify({ imageUrls: ["https://x/img1.jpg", "https://x/img2.jpg", "https://x/img3.jpg"] }),
    });

  const res = await POST(makeReq() as any); // 3 images exceeds guest's 2-scan limit
  const body = await res.json();

  expect(res.status).toBe(402);
  expect(body).toMatchObject({ reason: "scans", tier: "guest" });
  expect(callPipelineService).not.toHaveBeenCalled();
});
```

- [ ] **Step 3: Verify RED**

Run: `cd web && npx vitest run tests/integration/generateSamplePaper.route.test.ts`
Expected: FAIL — route module not found

- [ ] **Step 4: Write `web/src/app/api/generate-sample-paper/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { prisma } from "../../../lib/prismaClient";
import { checkAndConsumeQuota } from "../../../lib/quotaOrchestrator";
import { callPipelineService } from "../../../lib/pipelineClient";

export async function POST(req: Request) {
  const { userId } = auth();
  const body = await req.json();
  const imageUrls: string[] = body.imageUrls;
  const ip = req.headers.get("x-forwarded-for") ?? "0.0.0.0";

  const quota = await checkAndConsumeQuota(prisma, {
    clerkUserId: userId,
    ipAddress: ip,
    ipSalt: process.env.GUEST_IP_SALT!,
    scanCount: imageUrls.length,
  });

  if (!quota.allowed) {
    return NextResponse.json(
      { reason: quota.reason, tier: quota.tier, limit: quota.limit, used: quota.used },
      { status: 402 }
    );
  }

  const result = await callPipelineService(
    imageUrls,
    process.env.PIPELINE_SERVICE_URL!,
    process.env.PIPELINE_SERVICE_TOKEN!
  );

  return NextResponse.json(result, { status: 200 });
}
```

- [ ] **Step 5: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/generateSamplePaper.route.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/prismaClient.ts web/src/app/api/generate-sample-paper/ web/tests/integration/generateSamplePaper.route.test.ts
git commit -m "add Generate Sample Paper API route with pre-flight quota check"
```

---

### Task 13: Admin API — list + update tiers

**Files:**
- Create: `web/src/app/api/admin/tiers/route.ts` (GET),
  `web/src/app/api/admin/tiers/[id]/route.ts` (PATCH)
- Test: `web/tests/integration/tiersAdmin.route.test.ts`

**Interfaces:**
- Consumes: `recordAuditLog` (Task 10).
- Produces: `GET` returns `Tier[]`; `PATCH` updates one tier and writes
  one `AdminAuditLog` row per changed field.

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";
import { seedTiers } from "../../prisma/seed";

vi.mock("@clerk/nextjs/server", () => ({
  auth: () => ({ userId: "admin_1" }),
}));

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.adminAuditLog.deleteMany();
  await prisma.tier.deleteMany();
  await prisma.user.deleteMany();
  await prisma.user.create({ data: { id: "admin_1", email: "admin@example.com", role: "admin" } });
  await seedTiers(prisma);
});
afterAll(() => prisma.$disconnect());

test("GET lists all four seeded tiers", async () => {
  const { GET } = await import("../../src/app/api/admin/tiers/route");
  const res = await GET();
  const body = await res.json();
  expect(body).toHaveLength(4);
});

test("PATCH updates scansPerPeriod and writes one audit log entry for the changed field", async () => {
  const { PATCH } = await import("../../src/app/api/admin/tiers/[id]/route");
  const req = new Request("https://app.test/api/admin/tiers/guest", {
    method: "PATCH",
    body: JSON.stringify({ scansPerPeriod: 5 }),
  });

  const res = await PATCH(req as any, { params: { id: "guest" } });
  const body = await res.json();

  expect(body.scansPerPeriod).toBe(5);

  const logs = await prisma.adminAuditLog.findMany();
  expect(logs).toHaveLength(1);
  expect(logs[0]).toMatchObject({
    action: "tier.update",
    target: "guest.scansPerPeriod",
    oldValue: "2",
    newValue: "5",
  });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/tiersAdmin.route.test.ts`
Expected: FAIL — route modules not found

- [ ] **Step 3: Write `web/src/app/api/admin/tiers/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { prisma } from "../../../../lib/prismaClient";

export async function GET() {
  const tiers = await prisma.tier.findMany({ orderBy: { id: "asc" } });
  return NextResponse.json(tiers);
}
```

- [ ] **Step 4: Write `web/src/app/api/admin/tiers/[id]/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { prisma } from "../../../../../lib/prismaClient";
import { recordAuditLog } from "../../../../../lib/auditLog";

const EDITABLE_FIELDS = [
  "scansPerPeriod",
  "pdfsPerPeriod",
  "priceAmount",
  "currency",
  "billingInterval",
  "isActive",
] as const;

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const { userId } = auth();
  const before = await prisma.tier.findUniqueOrThrow({ where: { id: params.id as any } });
  const patch = await req.json();

  const data: Record<string, unknown> = {};
  for (const field of EDITABLE_FIELDS) {
    if (field in patch) data[field] = patch[field];
  }

  const after = await prisma.tier.update({
    where: { id: params.id as any },
    data: { ...data, updatedBy: userId },
  });

  for (const field of EDITABLE_FIELDS) {
    if (field in patch && String((before as any)[field]) !== String((after as any)[field])) {
      await recordAuditLog(prisma, {
        adminUserId: userId!,
        action: "tier.update",
        target: `${params.id}.${field}`,
        oldValue: String((before as any)[field]),
        newValue: String((after as any)[field]),
      });
    }
  }

  return NextResponse.json(after);
}
```

- [ ] **Step 5: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/tiersAdmin.route.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add web/src/app/api/admin/tiers/ web/tests/integration/tiersAdmin.route.test.ts
git commit -m "add admin tiers list + update API with per-field audit logging"
```

---

### Task 14: Admin API — usage lookup

**Files:**
- Create: `web/src/app/api/admin/usage/route.ts`
- Test: `web/tests/integration/usageAdmin.route.test.ts`

**Interfaces:**
- Produces: `GET /api/admin/usage?email=...` returns the matching user's
  current tier and usage-counter state, or `404`.

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.usageCounter.deleteMany();
  await prisma.user.deleteMany();
  await prisma.user.create({ data: { id: "user_1", email: "learner@example.com" } });
  await prisma.usageCounter.create({
    data: {
      identityType: "user",
      identityKey: "user_1",
      periodStart: new Date("2026-08-01T00:00:00Z"),
      periodEnd: new Date("2026-08-31T00:00:00Z"),
      scansUsed: 1,
      pdfsUsed: 0,
    },
  });
});
afterAll(() => prisma.$disconnect());

test("returns the matching user's usage counter by email", async () => {
  const { GET } = await import("../../src/app/api/admin/usage/route");
  const req = new Request("https://app.test/api/admin/usage?email=learner@example.com");

  const res = await GET(req as any);
  const body = await res.json();

  expect(res.status).toBe(200);
  expect(body).toMatchObject({ email: "learner@example.com", scansUsed: 1, pdfsUsed: 0 });
});

test("returns 404 when no user matches", async () => {
  const { GET } = await import("../../src/app/api/admin/usage/route");
  const req = new Request("https://app.test/api/admin/usage?email=nobody@example.com");

  const res = await GET(req as any);
  expect(res.status).toBe(404);
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/usageAdmin.route.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/app/api/admin/usage/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { prisma } from "../../../../lib/prismaClient";

export async function GET(req: Request) {
  const email = new URL(req.url).searchParams.get("email");
  const user = email ? await prisma.user.findUnique({ where: { email } }) : null;

  if (!user) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const counter = await prisma.usageCounter.findFirst({
    where: { identityType: "user", identityKey: user.id },
    orderBy: { periodEnd: "desc" },
  });

  return NextResponse.json({
    email: user.email,
    scansUsed: counter?.scansUsed ?? 0,
    pdfsUsed: counter?.pdfsUsed ?? 0,
    periodStart: counter?.periodStart ?? null,
    periodEnd: counter?.periodEnd ?? null,
  });
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/usageAdmin.route.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/app/api/admin/usage/ web/tests/integration/usageAdmin.route.test.ts
git commit -m "add admin usage lookup API"
```

---

### Task 15: Admin API — audit log listing

**Files:**
- Create: `web/src/app/api/admin/audit-log/route.ts`
- Test: `web/tests/integration/auditLogAdmin.route.test.ts`

**Interfaces:**
- Produces: `GET /api/admin/audit-log` returns entries newest-first.

- [ ] **Step 1: Write the failing test**

```typescript
import { PrismaClient } from "@prisma/client";
import { recordAuditLog } from "../../src/lib/auditLog";

const prisma = new PrismaClient({ datasources: { db: { url: process.env.DATABASE_URL_TEST } } });

beforeEach(async () => {
  await prisma.adminAuditLog.deleteMany();
  await prisma.user.deleteMany();
  await prisma.user.create({ data: { id: "admin_1", email: "admin@example.com", role: "admin" } });
  await recordAuditLog(prisma, { adminUserId: "admin_1", action: "tier.update", target: "guest.scansPerPeriod", oldValue: "2", newValue: "5" });
  await recordAuditLog(prisma, { adminUserId: "admin_1", action: "tier.update", target: "guest.pdfsPerPeriod", oldValue: "2", newValue: "5" });
});
afterAll(() => prisma.$disconnect());

test("returns audit log entries newest first", async () => {
  const { GET } = await import("../../src/app/api/admin/audit-log/route");
  const res = await GET();
  const body = await res.json();

  expect(body).toHaveLength(2);
  expect(body[0].target).toBe("guest.pdfsPerPeriod");
  expect(body[1].target).toBe("guest.scansPerPeriod");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/integration/auditLogAdmin.route.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/app/api/admin/audit-log/route.ts`**

```typescript
import { NextResponse } from "next/server";
import { prisma } from "../../../../lib/prismaClient";

export async function GET() {
  const entries = await prisma.adminAuditLog.findMany({ orderBy: { createdAt: "desc" } });
  return NextResponse.json(entries);
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/integration/auditLogAdmin.route.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add web/src/app/api/admin/audit-log/ web/tests/integration/auditLogAdmin.route.test.ts
git commit -m "add admin audit log listing API"
```

---

### Task 16: Admin UI — Tiers screen

**Files:**
- Create: `web/src/app/admin/tiers/page.tsx`
- Test: `web/tests/components/TiersScreen.test.tsx`

**Interfaces:**
- Consumes: `GET`/`PATCH /api/admin/tiers` (Task 13) via `fetch`.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TiersPage from "../../src/app/admin/tiers/page";

test("renders each tier fetched from the API with its current scan limit", async () => {
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => [
      { id: "guest", name: "Guest", scansPerPeriod: 2, pdfsPerPeriod: 2, priceAmount: null, currency: null, billingInterval: "none", isActive: true },
    ],
  }) as any;

  render(<TiersPage />);

  await waitFor(() => screen.getByTestId("tier-row-guest"));
  expect(screen.getByLabelText("guest-scans")).toHaveValue(2);
});

test("editing a limit and clicking Save PATCHes the tier with the new value", async () => {
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => [
      { id: "guest", name: "Guest", scansPerPeriod: 2, pdfsPerPeriod: 2, priceAmount: null, currency: null, billingInterval: "none", isActive: true },
    ],
  }) as any;

  render(<TiersPage />);
  await waitFor(() => screen.getByTestId("tier-row-guest"));

  const input = screen.getByLabelText("guest-scans");
  await userEvent.clear(input);
  await userEvent.type(input, "5");
  await userEvent.click(screen.getByText("Save"));

  expect(fetch).toHaveBeenLastCalledWith(
    "/api/admin/tiers/guest",
    expect.objectContaining({ method: "PATCH" })
  );
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/components/TiersScreen.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/app/admin/tiers/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";

interface TierRow {
  id: string;
  name: string;
  scansPerPeriod: number;
  pdfsPerPeriod: number;
  priceAmount: number | null;
  currency: string | null;
  billingInterval: string;
  isActive: boolean;
}

export default function TiersPage() {
  const [tiers, setTiers] = useState<TierRow[]>([]);

  useEffect(() => {
    fetch("/api/admin/tiers").then((r) => r.json()).then(setTiers);
  }, []);

  async function save(tier: TierRow) {
    await fetch(`/api/admin/tiers/${tier.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scansPerPeriod: tier.scansPerPeriod,
        pdfsPerPeriod: tier.pdfsPerPeriod,
      }),
    });
  }

  return (
    <table>
      <tbody>
        {tiers.map((tier) => (
          <tr key={tier.id} data-testid={`tier-row-${tier.id}`}>
            <td>{tier.name}</td>
            <td>
              <input
                aria-label={`${tier.id}-scans`}
                type="number"
                value={tier.scansPerPeriod}
                onChange={(e) =>
                  setTiers((prev) =>
                    prev.map((t) =>
                      t.id === tier.id ? { ...t, scansPerPeriod: Number(e.target.value) } : t
                    )
                  )
                }
              />
            </td>
            <td>
              <button onClick={() => save(tier)}>Save</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/components/TiersScreen.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/app/admin/tiers/page.tsx web/tests/components/TiersScreen.test.tsx
git commit -m "add admin Tiers screen"
```

---

### Task 17: Admin UI — Usage lookup screen

**Files:**
- Create: `web/src/app/admin/usage/page.tsx`
- Test: `web/tests/components/UsageLookupScreen.test.tsx`

**Interfaces:**
- Consumes: `GET /api/admin/usage?email=...` (Task 14) via `fetch`.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UsageLookupPage from "../../src/app/admin/usage/page";

test("searching by email displays the returned usage", async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ email: "learner@example.com", scansUsed: 1, pdfsUsed: 0, periodStart: null, periodEnd: null }),
  }) as any;

  render(<UsageLookupPage />);

  await userEvent.type(screen.getByLabelText("email"), "learner@example.com");
  await userEvent.click(screen.getByText("Search"));

  expect(await screen.findByText(/scans used: 1/i)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/admin/usage?email=learner%40example.com");
});

test("shows a not-found message on a 404", async () => {
  global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 }) as any;

  render(<UsageLookupPage />);
  await userEvent.type(screen.getByLabelText("email"), "nobody@example.com");
  await userEvent.click(screen.getByText("Search"));

  expect(await screen.findByText(/no user found/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/components/UsageLookupScreen.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/app/admin/usage/page.tsx`**

```tsx
"use client";
import { useState } from "react";

interface UsageResult {
  email: string;
  scansUsed: number;
  pdfsUsed: number;
  periodStart: string | null;
  periodEnd: string | null;
}

export default function UsageLookupPage() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<UsageResult | null>(null);
  const [notFound, setNotFound] = useState(false);

  async function search() {
    setNotFound(false);
    setResult(null);
    const res = await fetch(`/api/admin/usage?email=${encodeURIComponent(email)}`);
    if (!res.ok) {
      setNotFound(true);
      return;
    }
    setResult(await res.json());
  }

  return (
    <div>
      <label>
        email
        <input aria-label="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <button onClick={search}>Search</button>

      {result && (
        <p>
          Scans used: {result.scansUsed} — PDFs used: {result.pdfsUsed}
        </p>
      )}
      {notFound && <p>No user found</p>}
    </div>
  );
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/components/UsageLookupScreen.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src/app/admin/usage/page.tsx web/tests/components/UsageLookupScreen.test.tsx
git commit -m "add admin usage lookup screen"
```

---

### Task 18: Admin UI — Audit log screen

**Files:**
- Create: `web/src/app/admin/audit-log/page.tsx`
- Test: `web/tests/components/AuditLogScreen.test.tsx`

**Interfaces:**
- Consumes: `GET /api/admin/audit-log` (Task 15) via `fetch`.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import AuditLogPage from "../../src/app/admin/audit-log/page";

test("renders each audit log entry fetched from the API", async () => {
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => [
      {
        id: "log_1",
        adminUserId: "admin_1",
        action: "tier.update",
        target: "guest.scansPerPeriod",
        oldValue: "2",
        newValue: "5",
        createdAt: "2026-08-18T00:00:00Z",
      },
    ],
  }) as any;

  render(<AuditLogPage />);

  await waitFor(() => screen.getByText("guest.scansPerPeriod"));
  expect(screen.getByText(/2.*5/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify RED**

Run: `cd web && npx vitest run tests/components/AuditLogScreen.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Write `web/src/app/admin/audit-log/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";

interface AuditLogRow {
  id: string;
  action: string;
  target: string;
  oldValue: string | null;
  newValue: string | null;
  createdAt: string;
}

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogRow[]>([]);

  useEffect(() => {
    fetch("/api/admin/audit-log").then((r) => r.json()).then(setEntries);
  }, []);

  return (
    <table>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id}>
            <td>{entry.createdAt}</td>
            <td>{entry.action}</td>
            <td>{entry.target}</td>
            <td>
              {entry.oldValue} → {entry.newValue}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Verify GREEN**

Run: `cd web && npx vitest run tests/components/AuditLogScreen.test.tsx`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add web/src/app/admin/audit-log/page.tsx web/tests/components/AuditLogScreen.test.tsx
git commit -m "add admin audit log screen"
```

---

## Explicitly not in this plan

- The FastAPI pipeline service's own internal-token auth check — that's a
  Python-side change tracked in the main `TODO.md`, not here.
- A concrete `SubscriptionProvider` implementation (Stripe/Clerk Billing)
  — deferred per the spec; `NotConfiguredProvider` is the only
  implementation this plan builds.
- Clerk webhook handling to mirror new sign-ups into the `User` table —
  needed before this is usable end-to-end, but not specified yet; flag
  before starting Task 12 if you want it added as a Task 12.5.
- Visual design of the admin screens — the components above are
  functional, unstyled HTML.
