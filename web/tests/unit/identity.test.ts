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
