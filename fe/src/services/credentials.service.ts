import { api } from "./api";

export interface Credential {
  uuid: string;
  name: string;
  description?: string;
  credential_type: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateCredentialDto {
  name: string;
  description?: string;
  credential_type: string;
  credential_data: Record<string, any>;
}

export interface UpdateCredentialDto {
  name?: string;
  description?: string;
  credential_type?: string;
  credential_data?: Record<string, any>;
}

interface ApiSuccessResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

class CredentialsServiceClass {
  async getAll(): Promise<Credential[]> {
    const res = await api.get<ApiSuccessResponse<Credential[]>>("/credentials");
    return res?.data ?? [];
  }

  async getByUuid(credentialUuid: string): Promise<Credential> {
    const res = await api.get<ApiSuccessResponse<Credential>>(`/credentials/${credentialUuid}`);
    return res?.data as Credential;
  }

  async create(dto: CreateCredentialDto): Promise<Credential> {
    const res = await api.post<ApiSuccessResponse<Credential>>("/credentials", dto);
    return res?.data as Credential;
  }

  async update(credentialUuid: string, dto: UpdateCredentialDto): Promise<Credential> {
    const res = await api.put<ApiSuccessResponse<Credential>>(`/credentials/${credentialUuid}`, dto);
    return res?.data as Credential;
  }

  async delete(credentialUuid: string): Promise<{ status: string; uuid: string }> {
    const res = await api.delete<ApiSuccessResponse<{ status: string; uuid: string }>>(`/credentials/${credentialUuid}`);
    return res?.data;
  }
}

export const CredentialsService = new CredentialsServiceClass();
export default CredentialsService;
