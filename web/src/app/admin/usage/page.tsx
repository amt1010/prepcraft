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
