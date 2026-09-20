import { API_ENDPOINTS } from "../constants/apiEndpoints";
import { api } from "./api";
import {
  WorkflowSummary,
  WorkflowDraft,
  WorkflowVersion,
  WorkflowDefinition,
  WorkflowUIMetadata,
  ValidationResponse,
} from "../types/workflow";

export interface CreateWorkflowDto {
  name: string;
  description?: string;
}

export interface UpdateWorkflowDto {
  name?: string;
  description?: string;
  status?: "active" | "archived";
}

export interface UpdateDraftDto {
  definition: WorkflowDefinition;
  ui_metadata?: WorkflowUIMetadata;
}

class WorkflowServiceClass {
  /**
   * List all workflows accessible to the current tenant context.
   */
  async listWorkflows(): Promise<WorkflowSummary[]> {
    const res = await api.get<any>(API_ENDPOINTS.WORKFLOWS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  /**
   * Get a single workflow container by ID.
   */
  async getWorkflow(workflowId: string): Promise<WorkflowSummary> {
    const res = await api.get<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}`);
    return res?.data ?? res;
  }

  /**
   * Create a new workflow container with an initial bootstrapped draft.
   */
  async createWorkflow(dto: CreateWorkflowDto): Promise<WorkflowSummary> {
    const res = await api.post<any>(API_ENDPOINTS.WORKFLOWS, dto);
    return res?.data ?? res;
  }

  /**
   * Update workflow metadata (name, description, status).
   */
  async updateWorkflow(workflowId: string, dto: UpdateWorkflowDto): Promise<WorkflowSummary> {
    const res = await api.patch<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}`, dto);
    return res?.data ?? res;
  }

  /**
   * Get mutable draft version for a workflow.
   */
  async getDraft(workflowId: string): Promise<WorkflowDraft> {
    const res = await api.get<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}/draft`);
    return res?.data ?? res;
  }

  /**
   * Save changes to the workflow mutable draft.
   */
  async saveDraft(
    workflowId: string,
    definition: WorkflowDefinition,
    ui_metadata?: WorkflowUIMetadata
  ): Promise<WorkflowDraft> {
    const payload: UpdateDraftDto = {
      definition,
      ui_metadata: ui_metadata || { positions: {} },
    };
    const res = await api.put<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}/draft`, payload);
    return res?.data ?? res;
  }

  /**
   * Validate a workflow definition without saving or publishing.
   */
  async validateWorkflow(workflowId: string, definition: WorkflowDefinition): Promise<ValidationResponse> {
    const res = await api.post<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}/validate`, {
      definition,
    });
    return res?.data ?? res;
  }

  /**
   * Publish the current draft into an immutable published version snapshot.
   */
  async publishWorkflow(workflowId: string, description?: string): Promise<WorkflowVersion> {
    const res = await api.post<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}/publish`, {
      description,
    });
    return res?.data ?? res;
  }

  /**
   * List all published immutable versions of a workflow.
   */
  async listVersions(workflowId: string): Promise<WorkflowVersion[]> {
    const res = await api.get<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}/versions`);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  /**
   * Get a specific published version snapshot by ID.
   */
  async getVersion(workflowId: string, versionId: string): Promise<WorkflowVersion> {
    const res = await api.get<any>(`${API_ENDPOINTS.WORKFLOWS}/${workflowId}/versions/${versionId}`);
    return res?.data ?? res;
  }
}

export const WorkflowService = new WorkflowServiceClass();
export default WorkflowService;
