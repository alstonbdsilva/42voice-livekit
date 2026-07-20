import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Client } from "@/types";

// ── DTOs ──────────────────────────────────────────────────────────────────────

export interface CreateClientDto {
  name: string;
  industry?: string;
  country?: string;
  monthlyRecurring?: number;
  contactEmail: string;
  resellerId: string; // required — provided by super_admin or injected server-side for reseller
}

export interface UpdateClientDto {
  name?: string;
  industry?: string;
  country?: string;
  monthlyRecurring?: number;
  contactEmail?: string;
  status?: "active" | "paused" | "inactive";
  resellerId?: string;
}

export interface ClientCredentials {
  email: string;
  password: string;
}

export interface CreateClientResponse {
  client: Client;
  credentials: ClientCredentials;
}

// ── API response shape ────────────────────────────────────────────────────────

interface ApiSuccessResponse<T> {
  success: true;
  message: string;
  data: T;
  meta: any;
}

// ── Mapper ────────────────────────────────────────────────────────────────────

function mapClient(raw: any): Client {
  return {
    id: raw.id,
    name: raw.name,
    industry: raw.industry ?? "",
    country: raw.country ?? "",
    monthlyRecurring: Number(raw.monthlyRecurring ?? raw.monthly_recurring ?? 0),
    contactEmail: raw.contactEmail ?? raw.contact_email,
    status: raw.status,
    createdAt: raw.createdAt ?? raw.created_at,
    resellerId: raw.resellerId ?? raw.reseller_id ?? undefined,
  };
}

// ── Service ───────────────────────────────────────────────────────────────────

class ClientServiceClass {
  /**
   * Fetch all clients visible to the current user.
   * The backend enforces reseller scoping via JWT claims.
   */
  async getAll(): Promise<Client[]> {
    const res = await api.get<ApiSuccessResponse<any[]>>(API_ENDPOINTS.CLIENTS);
    const list: any[] = res.data ?? [];
    return list.map(mapClient);
  }

  /**
   * Fetch a single client by ID.
   */
  async getById(id: string): Promise<Client> {
    const res = await api.get<ApiSuccessResponse<any>>(`${API_ENDPOINTS.CLIENTS}/${id}`);
    return mapClient(res.data);
  }

  /**
   * Create a new client.
   * For reseller role: the server ignores resellerId in the body and uses the JWT value.
   * For super_admin / finance_admin: resellerId in the DTO must be provided.
   */
  async create(dto: CreateClientDto): Promise<CreateClientResponse> {
    const res = await api.post<ApiSuccessResponse<{ client: any; credentials: ClientCredentials }>>(
      API_ENDPOINTS.CLIENTS,
      dto
    );
    const payload = res.data;
    return {
      client: mapClient(payload.client),
      credentials: payload.credentials,
    };
  }

  /**
   * Update an existing client.
   */
  async update(id: string, dto: UpdateClientDto): Promise<Client> {
    const res = await api.put<ApiSuccessResponse<any>>(`${API_ENDPOINTS.CLIENTS}/${id}`, dto);
    return mapClient(res.data);
  }

  /**
   * Delete a client.
   */
  async delete(id: string): Promise<void> {
    await api.delete(`${API_ENDPOINTS.CLIENTS}/${id}`);
  }
}

export const ClientService = new ClientServiceClass();
export default ClientService;
