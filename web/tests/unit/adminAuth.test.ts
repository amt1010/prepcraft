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
