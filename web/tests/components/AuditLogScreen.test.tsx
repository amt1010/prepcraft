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
