import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { User } from "@/types";

export interface CreateUserDto {
  email: string;
  firstName: string;
  lastName: string;
  phone?: string;
  roleName: string;
  resellerId?: string | null;
  clientId?: string | null;
}

export interface UpdateUserDto {
  email?: string;
  firstName?: string;
  lastName?: string;
  phone?: string | null;
  roleName?: string;
  resellerId?: string | null;
  clientId?: string | null;
  isActive?: boolean;
  isVerified?: boolean;
}

export interface UserCredentials {
  email: string;
  password?: string;
}

export interface CreateUserResponse {
  user: User;
  credentials: UserCredentials;
}

interface ApiSuccessResponse<T> {
  success: true;
  message: string;
  data: T;
  meta: any;
}

function mapUser(raw: any): User {
  return {
    id: raw.id,
    name: raw.name ?? `${raw.firstName} ${raw.lastName}`.trim(),
    email: raw.email,
    role: raw.role,
    status: raw.status,
    createdAt: raw.createdAt ?? raw.created_at,
    clientId: raw.clientId ?? raw.client_id ?? undefined,
    resellerId: raw.resellerId ?? raw.reseller_id ?? undefined,
    resellerName: raw.resellerName ?? raw.reseller_name ?? undefined,
    clientName: raw.clientName ?? raw.client_name ?? undefined,
  };
}

class UserServiceClass {
  async getAll(): Promise<User[]> {
    const res = await api.get<ApiSuccessResponse<any[]>>(API_ENDPOINTS.USERS);
    const list = res.data ?? [];
    return list.map(mapUser);
  }

  async getById(id: string): Promise<User> {
    const res = await api.get<ApiSuccessResponse<any>>(`${API_ENDPOINTS.USERS}/${id}`);
    return mapUser(res.data);
  }

  async create(dto: CreateUserDto): Promise<CreateUserResponse> {
    const res = await api.post<ApiSuccessResponse<{ user: any; credentials: UserCredentials }>>(
      API_ENDPOINTS.USERS,
      dto
    );
    const payload = res.data;
    return {
      user: mapUser(payload.user),
      credentials: payload.credentials,
    };
  }

  async update(id: string, dto: UpdateUserDto): Promise<User> {
    const res = await api.put<ApiSuccessResponse<any>>(`${API_ENDPOINTS.USERS}/${id}`, dto);
    return mapUser(res.data);
  }

  async delete(id: string): Promise<void> {
    await api.delete(`${API_ENDPOINTS.USERS}/${id}`);
  }
}

export const UserService = new UserServiceClass();
export default UserService;
