import { api } from "./api";

export interface TelephonyProviderFieldOption {
  label: string;
  value: string;
}

export interface VisibleWhenRule {
  field: string;
  equals: any;
}

export interface TelephonyProviderField {
  name: string;
  label: string;
  type: "text" | "password" | "textarea" | "number" | "boolean" | "select";
  required?: boolean;
  sensitive?: boolean;
  description?: string;
  placeholder?: string;
  section?: string;
  options?: TelephonyProviderFieldOption[];
  visible_when?: VisibleWhenRule;
}

export interface TelephonyProviderMetadata {
  provider: string;
  display_name: string;
  docs_url?: string;
  fields: TelephonyProviderField[];
}

export interface TelephonyConfigurationListItem {
  id: string;
  name: string;
  provider: string;
  is_default_outbound: boolean;
  phone_number_count: number;
  created_at: string;
  updated_at: string;
}

export interface TelephonyConfigurationDetail {
  id: string;
  name: string;
  provider: string;
  is_default_outbound: boolean;
  credentials: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface TelephonyPhoneNumberItem {
  id: string;
  telephony_configuration_id: string;
  address: string;
  address_type: string;
  country_code?: string;
  label?: string;
  is_active: boolean;
  is_default_caller_id: boolean;
  inbound_agent_id?: string;
  inbound_agent_name?: string;
  created_at: string;
  updated_at: string;
}

function extractData<T>(res: any): T {
  if (res && typeof res === "object" && "data" in res && res.data !== undefined) {
    return res.data;
  }
  return res;
}

export const TelephonyConfigService = {
  async getMetadata(): Promise<{ providers: TelephonyProviderMetadata[] }> {
    const res = await api.get("/telephony-configs/metadata");
    return extractData(res);
  },

  async listConfigurations(): Promise<{ configurations: TelephonyConfigurationListItem[] }> {
    const res = await api.get("/telephony-configs");
    return extractData(res);
  },

  async getConfiguration(configId: string): Promise<TelephonyConfigurationDetail> {
    const res = await api.get(`/telephony-configs/${configId}`);
    return extractData(res);
  },

  async createConfiguration(data: { name: string; is_default_outbound?: boolean; config: Record<string, any> }): Promise<TelephonyConfigurationDetail> {
    const res = await api.post("/telephony-configs", data);
    return extractData(res);
  },

  async updateConfiguration(configId: string, data: { name?: string; config?: Record<string, any> }): Promise<TelephonyConfigurationDetail> {
    const res = await api.put(`/telephony-configs/${configId}`, data);
    return extractData(res);
  },

  async deleteConfiguration(configId: string): Promise<void> {
    const res = await api.delete(`/telephony-configs/${configId}`);
    return extractData(res);
  },

  async setDefaultOutbound(configId: string): Promise<void> {
    const res = await api.post(`/telephony-configs/${configId}/set-default-outbound`);
    return extractData(res);
  },

  async listPhoneNumbers(configId: string): Promise<{ phone_numbers: TelephonyPhoneNumberItem[] }> {
    const res = await api.get(`/telephony-configs/${configId}/phone-numbers`);
    return extractData(res);
  },

  async addPhoneNumber(configId: string, data: {
    address: string;
    address_type?: string;
    country_code?: string;
    label?: string;
    is_active?: boolean;
    is_default_caller_id?: boolean;
    inbound_agent_id?: string;
  }): Promise<TelephonyPhoneNumberItem> {
    const res = await api.post(`/telephony-configs/${configId}/phone-numbers`, data);
    return extractData(res);
  },

  async updatePhoneNumber(configId: string, phoneNumberId: string, data: {
    address?: string;
    address_type?: string;
    country_code?: string;
    label?: string;
    is_active?: boolean;
    inbound_agent_id?: string;
  }): Promise<TelephonyPhoneNumberItem> {
    const res = await api.put(`/telephony-configs/${configId}/phone-numbers/${phoneNumberId}`, data);
    return extractData(res);
  },

  async deletePhoneNumber(configId: string, phoneNumberId: string): Promise<void> {
    const res = await api.delete(`/telephony-configs/${configId}/phone-numbers/${phoneNumberId}`);
    return extractData(res);
  },

  async setDefaultCallerId(configId: string, phoneNumberId: string): Promise<void> {
    const res = await api.post(`/telephony-configs/${configId}/phone-numbers/${phoneNumberId}/set-default-caller`);
    return extractData(res);
  },

  async initiateCall(data: {
    agent_id?: string;
    phone_number: string;
    telephony_configuration_id?: string;
    from_phone_number_id?: string;
  }): Promise<{ message?: string; call_id?: string }> {
    const res = await api.post("/telephony-configs/initiate-call", data);
    return extractData(res);
  }
};

export default TelephonyConfigService;
