export interface WorkflowSummary {
  id: string;
  clientId?: string;
  userId?: string;
  name: string;
  description?: string;
  status: "active" | "archived" | string;
  createdAt: string;
  updatedAt: string;
  latestPublishedVersionId?: string | null;
  latestPublishedVersionNumber?: number | null;
}

export type ConditionOperator =
  | "equals"
  | "not_equals"
  | "greater_than"
  | "greater_than_or_equal"
  | "less_than"
  | "less_than_or_equal"
  | "contains"
  | "exists"
  | "is_empty"
  | "is_not_empty"
  | "in"
  | "not_in";

export interface AtomicCondition {
  variable: string;
  operator: ConditionOperator;
  value?: any;
}

export interface CompositeCondition {
  and?: (AtomicCondition | CompositeCondition)[];
  or?: (AtomicCondition | CompositeCondition)[];
  not?: AtomicCondition | CompositeCondition;
}

export type WorkflowConditionSpec = AtomicCondition | CompositeCondition;

export interface ContextExposurePolicy {
  expose_variables?: string[];
  expose_initial_context?: string[];
  expose_gathered_context?: string[];
}

export interface WorkflowNode {
  id: string;
  name: string;
  type: "START" | "AGENT" | "CONDITION" | "END" | string;
  prompt?: string | null;
  tools?: string[];
  condition?: WorkflowConditionSpec | null;
  on_true?: string | null;
  on_false?: string | null;
  on_error?: string | null;
  transfer_config?: Record<string, any> | null;
  on_failure?: string | null;
  context_policy?: ContextExposurePolicy | null;
  config?: Record<string, any>;
  [key: string]: any;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type?: "default" | "semantic" | "deterministic" | "tool" | string;
  description?: string;
  condition?: WorkflowConditionSpec | null;
  priority?: number;
  required_variables?: string[];
  metadata?: Record<string, any>;
}

export interface WorkflowDefinition {
  version: number;
  workflow_id: string;
  name: string;
  start_node: string;
  global_prompt?: string;
  variables?: Record<string, any>;
  nodes: Record<string, WorkflowNode>;
  edges: WorkflowEdge[];
  model_config?: Record<string, any>;
  execution_config?: Record<string, any>;
}

export interface WorkflowUIMetadata {
  positions: Record<string, { x: number; y: number }>;
  viewport?: {
    x: number;
    y: number;
    zoom: number;
  };
  [key: string]: any;
}

export interface WorkflowDraft {
  id: string;
  workflow_id: string;
  version_number: number;
  lifecycle_status: "draft" | "published" | "archived" | string;
  definition: WorkflowDefinition;
  ui_metadata: WorkflowUIMetadata;
  validation_metadata?: {
    valid?: boolean;
    error_count?: number;
    warning_count?: number;
  };
  created_at?: string;
  published_at?: string | null;
  created_by?: string | null;
}

export interface WorkflowVersion {
  id: string;
  workflow_id: string;
  version_number: number;
  lifecycle_status: "draft" | "published" | "archived" | string;
  definition: WorkflowDefinition;
  ui_metadata: WorkflowUIMetadata;
  validation_metadata?: {
    valid?: boolean;
    error_count?: number;
    warning_count?: number;
  };
  created_at: string;
  published_at?: string | null;
  created_by?: string | null;
}

export interface ValidationErrorItem {
  code: string;
  message: string;
  node_id?: string | null;
  edge_id?: string | null;
}

export interface ValidationResponse {
  valid: boolean;
  errors: ValidationErrorItem[];
  warnings: ValidationErrorItem[];
  node_count: number;
  edge_count: number;
}

export interface ModelConfigSummary {
  id: string;
  clientId: string;
  name: string;
  description?: string;
  sttProvider: string;
  sttModel: string;
  sttLanguage?: string;
  llmProvider: string;
  llmModel: string;
  llmTemperature?: number;
  ttsProvider: string;
  ttsModel: string;
  ttsVoice?: string;
  isDefault: boolean;
  isActive: boolean;
  createdAt?: string;
  updatedAt?: string;
}
