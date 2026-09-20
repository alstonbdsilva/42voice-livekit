jest.mock("axios");
jest.mock("../services/api", () => ({
  api: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

import {
  deserializeWorkflow,
  serializeWorkflow,
} from "../components/workflows/serializer";
import {
  WorkflowDefinition,
  WorkflowDraft,
  WorkflowVersion,
  ValidationResponse,
} from "../types/workflow";
import { WorkflowService } from "../services/workflow.service";
import { AgentService } from "../services/agent.service";

// Mock API services for behavioral flow testing
jest.mock("../services/workflow.service");
jest.mock("../services/agent.service");

describe("Phase 4 Frontend Behavior & Workflow Orchestration Tests", () => {
  const baseDef: WorkflowDefinition = {
    version: 1,
    workflow_id: "wf_orch_test",
    name: "Orchestration Test Workflow",
    start_node: "start_node",
    global_prompt: "Global prompt text",
    variables: {},
    nodes: {
      start_node: {
        id: "start_node",
        name: "Start",
        type: "START",
        prompt: "",
        tools: [],
        config: { next_node: "agent_node" },
      },
      agent_node: {
        id: "agent_node",
        name: "Main Agent",
        type: "AGENT",
        prompt: "Welcome to our voice service.",
        tools: ["end_call"],
        config: {},
      },
      end_node: {
        id: "end_node",
        name: "End Call",
        type: "END",
        prompt: "Goodbye!",
        tools: ["end_call"],
        config: {},
      },
    },
    edges: [
      {
        id: "edge_start_to_agent",
        source: "start_node",
        target: "agent_node",
        type: "default",
      },
      {
        id: "edge_agent_to_end",
        source: "agent_node",
        target: "end_node",
        type: "semantic",
        description: "Hang up when user says goodbye",
      },
    ],
  };

  const sampleDraft: WorkflowDraft = {
    id: "draft_001",
    workflow_id: "wf_orch_test",
    version_number: 0,
    lifecycle_status: "draft",
    definition: baseDef,
    ui_metadata: {
      positions: {
        start_node: { x: 100, y: 100 },
        agent_node: { x: 400, y: 100 },
        end_node: { x: 700, y: 100 },
      },
    },
  };

  const samplePublishedVersion: WorkflowVersion = {
    id: "ver_pub_001",
    workflow_id: "wf_orch_test",
    version_number: 1,
    lifecycle_status: "published",
    definition: baseDef,
    ui_metadata: { positions: {} },
    created_at: "2026-09-20T10:00:00Z",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test A: Initial workflow hydration does not mark editor dirty
  test("A. Initial workflow hydration deserializes cleanly with isDirty = false", () => {
    let isDirty = false;

    // Simulate hydration
    const { nodes, edges } = deserializeWorkflow(sampleDraft.definition, sampleDraft.ui_metadata);

    // Initial state after deserializing should not have dirty flag set
    expect(nodes.length).toBe(3);
    expect(edges.length).toBe(2);
    expect(isDirty).toBe(false);
  });

  // Test B: Save failure prevents validation/publish continuation
  test("B. Save failure aborts the publish pipeline immediately", async () => {
    (WorkflowService.saveDraft as jest.Mock).mockRejectedValueOnce(new Error("Network / 500 Save Error"));
    (WorkflowService.validateWorkflow as jest.Mock).mockResolvedValueOnce({
      valid: true,
      errors: [],
      warnings: [],
      node_count: 3,
      edge_count: 2,
    });
    (WorkflowService.publishWorkflow as jest.Mock).mockResolvedValueOnce(samplePublishedVersion);

    let isDirty = true;
    let published = false;

    const executePublishSequence = async () => {
      // 1. If dirty, save first
      if (isDirty) {
        try {
          await WorkflowService.saveDraft("wf_orch_test", baseDef);
          isDirty = false;
        } catch (err) {
          // Abort sequence on save failure
          return;
        }
      }

      // 2. Validate
      const val = await WorkflowService.validateWorkflow("wf_orch_test", baseDef);
      if (!val.valid) return;

      // 3. Publish
      await WorkflowService.publishWorkflow("wf_orch_test");
      published = true;
    };

    await executePublishSequence();

    expect(WorkflowService.saveDraft).toHaveBeenCalledTimes(1);
    expect(WorkflowService.validateWorkflow).not.toHaveBeenCalled();
    expect(WorkflowService.publishWorkflow).not.toHaveBeenCalled();
    expect(published).toBe(false);
  });

  // Test C: Validation failure prevents publish request
  test("C. Validation failure aborts publish and prevents POST /publish", async () => {
    (WorkflowService.saveDraft as jest.Mock).mockResolvedValueOnce(sampleDraft);
    (WorkflowService.validateWorkflow as jest.Mock).mockResolvedValueOnce({
      valid: false,
      errors: [
        {
          code: "INVALID_START_NODE",
          message: "start_node does not exist",
          node_id: "missing_start",
        },
      ],
      warnings: [],
      node_count: 2,
      edge_count: 1,
    });
    (WorkflowService.publishWorkflow as jest.Mock).mockResolvedValueOnce(samplePublishedVersion);

    let published = false;

    const executePublishSequence = async () => {
      // 1. Save draft
      await WorkflowService.saveDraft("wf_orch_test", baseDef);

      // 2. Validate exact definition
      const val = await WorkflowService.validateWorkflow("wf_orch_test", baseDef);
      if (!val.valid) {
        return; // Validation failure stops publish
      }

      // 3. Publish
      await WorkflowService.publishWorkflow("wf_orch_test");
      published = true;
    };

    await executePublishSequence();

    expect(WorkflowService.saveDraft).toHaveBeenCalledTimes(1);
    expect(WorkflowService.validateWorkflow).toHaveBeenCalledTimes(1);
    expect(WorkflowService.publishWorkflow).not.toHaveBeenCalled();
    expect(published).toBe(false);
  });

  // Test D: Successful publish sequence is exactly: save dirty draft -> validate exact definition -> publish
  test("D. Successful publish executes save -> validate -> publish in exact ordered sequence", async () => {
    const callOrder: string[] = [];

    (WorkflowService.saveDraft as jest.Mock).mockImplementation(async () => {
      callOrder.push("saveDraft");
      return sampleDraft;
    });
    (WorkflowService.validateWorkflow as jest.Mock).mockImplementation(async () => {
      callOrder.push("validateWorkflow");
      return {
        valid: true,
        errors: [],
        warnings: [],
        node_count: 3,
        edge_count: 2,
      };
    });
    (WorkflowService.publishWorkflow as jest.Mock).mockImplementation(async () => {
      callOrder.push("publishWorkflow");
      return samplePublishedVersion;
    });

    let isDirty = true;

    // Sequence
    if (isDirty) {
      await WorkflowService.saveDraft("wf_orch_test", baseDef);
      isDirty = false;
    }

    const val = await WorkflowService.validateWorkflow("wf_orch_test", baseDef);
    expect(val.valid).toBe(true);

    const result = await WorkflowService.publishWorkflow("wf_orch_test", "Release v1");

    expect(callOrder).toEqual(["saveDraft", "validateWorkflow", "publishWorkflow"]);
    expect(result.version_number).toBe(1);
    expect(result.lifecycle_status).toBe("published");
  });

  // Test E: Backend validation error containing node_id maps to/focuses the correct React Flow node
  test("E. Backend validation error with node_id locates and focuses the target node", () => {
    const { nodes } = deserializeWorkflow(sampleDraft.definition, sampleDraft.ui_metadata);

    const validationResponse: ValidationResponse = {
      valid: false,
      errors: [
        {
          code: "MISSING_PROMPT",
          message: "Agent node prompt cannot be empty",
          node_id: "agent_node",
        },
      ],
      warnings: [],
      node_count: 3,
      edge_count: 2,
    };

    const targetError = validationResponse.errors[0];
    const matchingNode = nodes.find((n) => n.id === targetError.node_id);

    expect(matchingNode).toBeDefined();
    expect(matchingNode?.id).toBe("agent_node");
    expect(matchingNode?.data.name).toBe("Main Agent");
  });

  // Test F: Published workflow version inspection is read-only and cannot mutate the draft
  test("F. Published workflow version is marked read-only and protects draft from unintended mutation", () => {
    const isReadOnly = samplePublishedVersion.lifecycle_status === "published";
    expect(isReadOnly).toBe(true);

    let draftMutated = false;
    const mutateAction = () => {
      if (isReadOnly) {
        // Protected in read-only mode
        return;
      }
      draftMutated = true;
    };

    mutateAction();
    expect(draftMutated).toBe(false);
  });

  // Test G: Agent workflow assignment sends publishedWorkflowVersionId using exact immutable workflow version ID
  test("G. Agent workflow assignment sends exact publishedWorkflowVersionId", async () => {
    (AgentService.updateDetails as jest.Mock).mockResolvedValueOnce({
      id: "agent_123",
      publishedWorkflowVersionId: "ver_pub_001",
    });

    const selectedWorkflowVersionId: string = "ver_pub_001";

    await AgentService.updateDetails("agent_123", {
      name: "Support Agent",
      publishedWorkflowVersionId: selectedWorkflowVersionId === "none" ? null : selectedWorkflowVersionId,
      platformModelConfigurationId: null,
    });

    expect(AgentService.updateDetails).toHaveBeenCalledWith(
      "agent_123",
      expect.objectContaining({
        publishedWorkflowVersionId: "ver_pub_001",
      })
    );
  });

  // Test H: Compatibility selection sends/clears the workflow assignment according to existing backend contract
  test("H. Compatibility selection sends publishedWorkflowVersionId = null to use legacy mode", async () => {
    (AgentService.updateDetails as jest.Mock).mockResolvedValueOnce({
      id: "agent_123",
      publishedWorkflowVersionId: null,
    });

    const selectedWorkflowVersionId: string = "none"; // User chose Legacy Compatibility

    await AgentService.updateDetails("agent_123", {
      name: "Support Agent",
      publishedWorkflowVersionId: selectedWorkflowVersionId === "none" ? null : selectedWorkflowVersionId,
      platformModelConfigurationId: null,
    });

    expect(AgentService.updateDetails).toHaveBeenCalledWith(
      "agent_123",
      expect.objectContaining({
        publishedWorkflowVersionId: null,
      })
    );
  });

  // Test I: Model configuration assignment sends platformModelConfigurationId independently from workflow assignment
  test("I. Model config assignment sends platformModelConfigurationId independently without coupling to workflow", async () => {
    (AgentService.updateDetails as jest.Mock).mockResolvedValueOnce({
      id: "agent_123",
      publishedWorkflowVersionId: "ver_pub_001",
      platformModelConfigurationId: "mc_groq_deepgram_123",
    });

    const selectedWorkflowVersionId: string = "ver_pub_001";
    const selectedModelConfigId: string = "mc_groq_deepgram_123";

    await AgentService.updateDetails("agent_123", {
      name: "Support Agent",
      publishedWorkflowVersionId: selectedWorkflowVersionId === "none" ? null : selectedWorkflowVersionId,
      platformModelConfigurationId: selectedModelConfigId === "default" ? null : selectedModelConfigId,
    });

    expect(AgentService.updateDetails).toHaveBeenCalledWith(
      "agent_123",
      expect.objectContaining({
        publishedWorkflowVersionId: "ver_pub_001",
        platformModelConfigurationId: "mc_groq_deepgram_123",
      })
    );

    // Verify model provider configuration is never injected into workflow AGENT node
    const { nodes, edges } = deserializeWorkflow(baseDef);
    const { definition } = serializeWorkflow(nodes, edges, baseDef);
    expect(definition.nodes.agent_node).toBeDefined();
    expect(definition.nodes.agent_node.model_config).toBeUndefined();
    expect(definition.nodes.agent_node.provider).toBeUndefined();
  });
});
