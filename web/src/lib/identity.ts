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
