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
