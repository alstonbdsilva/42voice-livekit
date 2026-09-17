import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import TelephonyConfigService from "./telephonyConfigService";

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
    const list: any[] = [];

    // 1. Fetch phone numbers from Telephony Configurations API (/telephony-configs)
    try {
      const configRes = await TelephonyConfigService.listConfigurations();
      const configs = configRes?.configurations || [];
      for (const cfg of configs) {
        try {
          const numRes = await TelephonyConfigService.listPhoneNumbers(cfg.id);
          const numbers = numRes?.phone_numbers || [];
          for (const item of numbers) {
            list.push({
              id: item.id,
              number: item.address,
              address: item.address,
              name: item.label ? `${item.address} (${item.label})` : item.address,
              label: item.label,
              provider: cfg.provider,
              configId: cfg.id,
              telephony_configuration_id: cfg.id,
              agentId: item.inbound_agent_id,
              inbound_agent_id: item.inbound_agent_id,
              inbound_agent_name: item.inbound_agent_name,
              is_active: item.is_active,
              is_default_caller_id: item.is_default_caller_id,
              created_at: item.created_at,
              updated_at: item.updated_at,
            });
          }
        } catch (err) {
          console.error(`Failed to load numbers for configuration ${cfg.id}:`, err);
        }
      }
    } catch (err) {
      console.error("Failed to load telephony configurations for phone numbers:", err);
    }

    // 2. Fallback / merge from legacy phone-numbers API
    try {
      const url = status 
        ? `${API_ENDPOINTS.PHONE_NUMBERS}?status=${status}`
        : API_ENDPOINTS.PHONE_NUMBERS;
      const res = await api.get<any>(url);
      const data = res?.data ?? res;
      const legacyArr = Array.isArray(data) ? data : (data?.data ?? []);
      for (const item of legacyArr) {
        if (!list.some((existing) => existing.id === item.id || existing.number === item.number)) {
          list.push({
            ...item,
            address: item.address || item.number,
            number: item.number || item.address,
            agentId: item.agentId || item.inbound_agent_id,
          });
        }
      }
    } catch (err) {
      // Legacy API may be deprecated or unpopulated
    }

    return list;
  }

  async getAvailable(country = "US", type = "Local", areaCode?: string): Promise<any[]> {
    try {
      const params = new URLSearchParams({ country, type });
      if (areaCode) params.append("areaCode", areaCode);
      const res = await api.get<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/available?${params.toString()}`);
      const data = res?.data ?? res;
      return Array.isArray(data) ? data : (data?.data ?? []);
    } catch (err) {
      return [];
    }
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

  async assignAgent(id: string, agentId: string | null): Promise<any> {
    // Check if phone number belongs to new Telephony Configurations API
    try {
      const allNumbers = await this.getAll();
      const target = allNumbers.find((n) => n.id === id);
      if (target && target.telephony_configuration_id) {
        return await TelephonyConfigService.updatePhoneNumber(
          target.telephony_configuration_id,
          id,
          { inbound_agent_id: agentId || undefined }
        );
      }
    } catch (err) {
      console.error("Failed to lookup telephony configuration for phone number assignment:", err);
    }

    // Fallback to legacy endpoint
    const res = await api.patch<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}/assign-agent`, { agentId });
    return res?.data ?? res;
  }

  async getLiveKitStatus(): Promise<any> {
    const res = await api.get<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/livekit-status`);
    return res?.data ?? res;
  }

  async deleteLiveKitTrunk(trunkId: string): Promise<any> {
    const res = await api.delete<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/livekit/trunk/${trunkId}`);
    return res?.data ?? res;
  }

  async deleteLiveKitDispatchRule(ruleId: string): Promise<any> {
    const res = await api.delete<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/livekit/dispatch-rule/${ruleId}`);
    return res?.data ?? res;
  }

  async update(id: string, dto: any): Promise<any> {
    const res = await api.put<any>(`${API_ENDPOINTS.PHONE_NUMBERS}/${id}`, dto);
    return res?.data ?? res;
  }
}

export const PhoneNumberService = new PhoneNumberServiceClass();
export default PhoneNumberService;
