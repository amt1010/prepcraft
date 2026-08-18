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
