import StartNode from "./StartNode";
import AgentNode from "./AgentNode";
import ConditionNode from "./ConditionNode";
import EndNode from "./EndNode";
import UnknownNode from "./UnknownNode";

export const nodeTypes = {
  startNode: StartNode,
  agentNode: AgentNode,
  conditionNode: ConditionNode,
  endNode: EndNode,
  unknownNode: UnknownNode,
};

export { StartNode, AgentNode, ConditionNode, EndNode, UnknownNode };
