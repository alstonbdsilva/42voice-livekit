import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Payment } from "@/types";

class PaymentServiceClass {
  async getAll(): Promise<Payment[]> {
    const res = await api.get<any>(API_ENDPOINTS.PAYMENTS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }
}

export const PaymentService = new PaymentServiceClass();
export default PaymentService;
