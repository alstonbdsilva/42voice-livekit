import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Contract } from "@/types";

interface ApiSuccessResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

class ContractServiceClass {
  async getAll(): Promise<Contract[]> {
    const res = await api.get<any>(API_ENDPOINTS.CONTRACTS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  async getById(id: string): Promise<Contract> {
    const res = await api.get<any>(`${API_ENDPOINTS.CONTRACTS}/${id}`);
    const data = res?.data ?? res;
    return data;
  }

  async create(dto: {
    clientId: string;
    contractValue: number;
    startDate: string;
    endDate: string;
    autoRenewal?: boolean;
    paymentTerms?: string;
    billingCycle?: string;
    noticePeriodDays?: number;
    notes?: string;
  }): Promise<Contract> {
    const res = await api.post<ApiSuccessResponse<Contract>>(API_ENDPOINTS.CONTRACTS, dto);
    const data = res?.data ?? res;
    return data;
  }

  async update(id: string, dto: {
    status?: string;
    contractValue?: number;
    endDate?: string;
    autoRenewal?: boolean;
    notes?: string;
  }): Promise<Contract> {
    const res = await api.put<ApiSuccessResponse<Contract>>(`${API_ENDPOINTS.CONTRACTS}/${id}`, dto);
    const data = res?.data ?? res;
    return data;
  }
}

export const ContractService = new ContractServiceClass();
export default ContractService;
