import { BillingNotConfiguredError, type SubscriptionProvider } from "./SubscriptionProvider";

export class NotConfiguredProvider implements SubscriptionProvider {
  async createCheckoutSession(): Promise<{ checkoutUrl: string }> {
    throw new BillingNotConfiguredError();
  }
  async handleWebhook(): Promise<never> {
    throw new BillingNotConfiguredError();
  }
  async cancelSubscription(): Promise<void> {
    throw new BillingNotConfiguredError();
  }
}
