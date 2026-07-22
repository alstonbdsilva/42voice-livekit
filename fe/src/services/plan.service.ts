import { api } from "./api";

export interface Plan {
  id: string;
  name: string;
  description: string;
  price: number;
  minutes: number;
  isCustom: boolean;
  resellerId?: string;
  status: string;
  createdAt: string;
  clientPrice?: number;
  resellerPlanStatus?: string;
}

export interface CreatePlanDto {
  name: string;
  description?: string;
  price: number;
  minutes: number;
  isCustom?: boolean;
  resellerId?: string;
}

export interface UpdatePlanDto {
  name?: string;
  description?: string;
  price?: number;
  minutes?: number;
  status?: string;
}

class PlanServiceClass {
  async getAll(): Promise<Plan[]> {
    const res = await api.get<any>("/plans");
    const data = res?.data ?? res ?? [];
    return data;
  }

  async create(dto: CreatePlanDto): Promise<Plan> {
    const res = await api.post<any>("/plans", dto);
    return res?.data ?? res;
  }

  async update(id: string, dto: UpdatePlanDto): Promise<Plan> {
    const res = await api.put<any>(`/plans/${id}`, dto);
    return res?.data ?? res;
  }

  async setRate(id: string, clientPrice: number, status: string = "active"): Promise<any> {
    const res = await api.post<any>(`/plans/${id}/set-rate`, { clientPrice, status });
    return res?.data ?? res;
  }
}

export const PlanService = new PlanServiceClass();
export default PlanService;
