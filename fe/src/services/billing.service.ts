import { api } from "./api";

export interface BuyPlanResponse {
  checkout_url: string;
}

class BillingServiceClass {
  async buyPlan(planId: string): Promise<string> {
    const res = await api.post<any>("/billing/buy-plan", { planId });
    const payload = res?.data ?? res;
    return payload.checkout_url;
  }

  async simulateSuccess(dto: {
    planId: string;
    buyerType: string;
    buyerId: string;
    price: number;
    reference?: string;
  }): Promise<any> {
    const res = await api.post<any>("/billing/mock-success", {
      planId: dto.planId,
      buyerType: dto.buyerType,
      buyerId: dto.buyerId,
      price: dto.price,
      reference: dto.reference
    });
    return res;
  }
}

export const BillingService = new BillingServiceClass();
export default BillingService;
