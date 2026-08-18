export interface SubscriptionEvent {
  userId: string;
  tierId: string;
  status: "active" | "canceled" | "past_due";
  currentPeriodEnd: Date;
}

export interface SubscriptionProvider {
  createCheckoutSession(userId: string, tierId: string): Promise<{ checkoutUrl: string }>;
  handleWebhook(payload: unknown, signature: string): Promise<SubscriptionEvent>;
  cancelSubscription(externalSubscriptionId: string): Promise<void>;
}

export class BillingNotConfiguredError extends Error {
  constructor() {
    super("No billing provider is configured yet — subscriptions cannot be created.");
    this.name = "BillingNotConfiguredError";
  }
}
