import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Invoice } from "@/types";

interface ApiSuccessResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

class InvoiceServiceClass {
  async getAll(): Promise<Invoice[]> {
    const res = await api.get<any>(API_ENDPOINTS.INVOICES);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  async getById(id: string): Promise<Invoice> {
    const res = await api.get<any>(`${API_ENDPOINTS.INVOICES}/${id}`);
    const data = res?.data ?? res;
    return data;
  }

  async create(dto: {
    clientId?: string;
    resellerId?: string;
    amount: number;
    tax?: number;
    total: number;
    dueDate: string;
    lineItems?: Array<{ description: string; amount: number }>;
  }): Promise<Invoice> {
    const res = await api.post<ApiSuccessResponse<Invoice>>(API_ENDPOINTS.INVOICES, dto);
    const data = res?.data ?? res;
    return data;
  }

  async update(id: string, dto: {
    status: string;
    paidAmount?: number;
  }): Promise<Invoice> {
    const res = await api.put<ApiSuccessResponse<Invoice>>(`${API_ENDPOINTS.INVOICES}/${id}`, dto);
    const data = res?.data ?? res;
    return data;
  }
}

export const InvoiceService = new InvoiceServiceClass();
export default InvoiceService;
