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
