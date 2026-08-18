export interface SessionClaims {
  role?: string;
}

export function isAdminSession(claims: SessionClaims | null): boolean {
  return claims?.role === "admin";
}
