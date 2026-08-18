import { NotConfiguredProvider } from "../../src/lib/billing/NotConfiguredProvider";
import { BillingNotConfiguredError } from "../../src/lib/billing/SubscriptionProvider";

test("createCheckoutSession throws BillingNotConfiguredError", async () => {
  const provider = new NotConfiguredProvider();
  await expect(provider.createCheckoutSession("user_1", "subscribed_monthly")).rejects.toThrow(
    BillingNotConfiguredError
  );
});

test("cancelSubscription throws BillingNotConfiguredError", async () => {
  const provider = new NotConfiguredProvider();
  await expect(provider.cancelSubscription("sub_123")).rejects.toThrow(BillingNotConfiguredError);
});
