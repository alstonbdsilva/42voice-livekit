import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Renewal } from "@/types";

class RenewalServiceClass {
  async getAll(): Promise<Renewal[]> {
    const res = await api.get<any>(API_ENDPOINTS.RENEWALS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }
}

export const RenewalService = new RenewalServiceClass();
export default RenewalService;
