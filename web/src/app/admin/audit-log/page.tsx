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
