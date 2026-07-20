import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Reseller } from "@/types";

// ---- Request / Response DTOs ------------------------------------------------

export interface CreateResellerDto {
  name: string;
  contactEmail: string;
  country: string;
  commissionPct: number;
}

export interface UpdateResellerDto {
  name?: string;
  contactEmail?: string;
  country?: string;
  commissionPct?: number;
  status?: "active" | "inactive";
}

export interface ResellerCredentials {
  email: string;
  password: string;
}

export interface CreateResellerResponse {
  reseller: Reseller;
  credentials: ResellerCredentials;
}

// ---- Backend response shape --------------------------------------------------

interface ApiSuccessResponse<T> {
  success: true;
  message: string;
  data: T;
  meta: any;
}

// ---- Mapping helper ----------------------------------------------------------

function mapReseller(raw: any): Reseller {
  return {
    id: raw.id,
    name: raw.name,
    country: raw.country,
    commissionPct: Number(raw.commissionPct ?? raw.commission_pct),
    contactEmail: raw.contactEmail ?? raw.contact_email,
    status: raw.status,
    createdAt: raw.createdAt ?? raw.created_at,
  };
}

// ---- Service class -----------------------------------------------------------

class ResellerServiceClass {
  /**
   * Fetch all resellers / distribution partners.
   */
  async getAll(): Promise<Reseller[]> {
    const res = await api.get<any>(API_ENDPOINTS.RESELLERS);
    const list: any[] = Array.isArray(res) ? res : (res?.data ?? []);
    return list.map(mapReseller);
  }

  /**
   * Fetch a single reseller by ID.
   */
  async getById(id: string): Promise<Reseller> {
    const res = await api.get<any>(`${API_ENDPOINTS.RESELLERS}/${id}`);
    const data = res?.data ?? res;
    return mapReseller(data);
  }

  /**
   * Create a new reseller partner.
   * Returns the created Reseller plus the generated temporary credentials.
   */
  async create(dto: CreateResellerDto): Promise<CreateResellerResponse> {
    const res = await api.post<ApiSuccessResponse<{ reseller: any; credentials: ResellerCredentials }>>(
      API_ENDPOINTS.RESELLERS,
      dto
    );
    const payload = res.data;
    return {
      reseller: mapReseller(payload.reseller),
      credentials: payload.credentials,
    };
  }

  /**
   * Update an existing reseller.
   */
  async update(id: string, dto: UpdateResellerDto): Promise<Reseller> {
    const res = await api.put<ApiSuccessResponse<any>>(`${API_ENDPOINTS.RESELLERS}/${id}`, dto);
    return mapReseller(res.data);
  }

  /**
   * Delete a reseller and their linked user account.
   */
  async delete(id: string): Promise<void> {
    await api.delete(`${API_ENDPOINTS.RESELLERS}/${id}`);
  }
}

export const ResellerService = new ResellerServiceClass();
export default ResellerService;
