import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Commission } from "@/types";

interface ApiSuccessResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

class CommissionServiceClass {
  async getAll(): Promise<Commission[]> {
    const res = await api.get<any>(API_ENDPOINTS.COMMISSIONS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  async processPayout(id: string): Promise<any> {
    const res = await api.post<ApiSuccessResponse<any>>(`${API_ENDPOINTS.COMMISSIONS}/${id}/payout`);
    const data = res?.data ?? res;
    return data;
  }
}

export const CommissionService = new CommissionServiceClass();
export default CommissionService;
