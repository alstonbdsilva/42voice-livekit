import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { DashboardMoney, DashboardSummary } from "@/types";

class FinanceServiceClass {
  async getDashboardSummary(): Promise<DashboardSummary> {
    const res = await api.get<any>(API_ENDPOINTS.DASHBOARD_SUMMARY);
    const data = res?.data ?? res;
    return data;
  }

  async getDashboardMoney(): Promise<DashboardMoney> {
    const res = await api.get<any>(API_ENDPOINTS.DASHBOARD_MONEY);
    const data = res?.data ?? res;
    return data;
  }
}

export const FinanceService = new FinanceServiceClass();
export default FinanceService;
