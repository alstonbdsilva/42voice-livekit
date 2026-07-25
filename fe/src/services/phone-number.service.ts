import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";

export interface RegisterPhoneNumberDto {
  number: string;
  name?: string;
  provider: "Twilio" | "CITL";
  monthlyCost: number;
  setupCost: number;
  capabilities: { voice: boolean; sms: boolean };
  sipConfig?: any;
  allocation: "pool" | "me" | "client" | "reseller";
  assignedId?: string;
  draft?: boolean;
}

export interface LeasePhoneNumberDto {
  name?: string;
  agentId?: string;
}

class PhoneNumberServiceClass {
  async getAll(status?: string): Promise<any[]> {
    const url = status 
      ? `${API_ENDPOINTS.PHONE_NUMBERS}?status=${status}`
      : API_ENDPOINTS.PHONE_NUMBERS;
    const res = await api.get<any>(url);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  async register(dto: RegisterPhoneNumberDto): Promise<any> {
    const res = await api.post<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/register`, dto);
    return res?.data ?? res;
  }

  async lease(id: string, dto: LeasePhoneNumberDto): Promise<any> {
    const res = await api.post<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}/lease`, dto);
    return res?.data ?? res;
  }

  async release(id: string): Promise<any> {
    const res = await api.post<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}/release`);
    return res?.data ?? res;
  }

  async assignAgent(id: string, agentId: string): Promise<any> {
    const res = await api.patch<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}/assign-agent`, { agentId });
    return res?.data ?? res;
  }

  async getLiveKitStatus(): Promise<any> {
    const res = await api.get<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/livekit-status`);
    return res?.data ?? res;
  }

  async update(id: string, dto: any): Promise<any> {
    const res = await api.put<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}`, dto);
    return res?.data ?? res;
  }
}

export const PhoneNumberService = new PhoneNumberServiceClass();
export default PhoneNumberService;
