import { BillingNotConfiguredError, type SubscriptionProvider } from "./SubscriptionProvider";

export class NotConfiguredProvider implements SubscriptionProvider {
  async createCheckoutSession(_userId: string, _tierId: string): Promise<{ checkoutUrl: string }> {
    throw new BillingNotConfiguredError();
  }
  async handleWebhook(_payload: unknown, _signature: string): Promise<never> {
    throw new BillingNotConfiguredError();
  }
  async cancelSubscription(_externalSubscriptionId: string): Promise<void> {
    throw new BillingNotConfiguredError();
  }
}
