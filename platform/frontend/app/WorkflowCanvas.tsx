"use client";

import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import { Button, Empty, Space, Tag, Typography } from "antd";
import { useEffect, useMemo } from "react";

const { Text } = Typography;

type Contract = {
  type: string;
  properties: Record<string, { type: string }>;
  required: string[];
};

export type WorkflowDefinition = {
  nodes: {
    id: string;
    type: string;
    tool_id?: string;
    inputs: Contract;
    outputs: Contract;
  }[];
  edges: { from: string; to: string }[];
};

type FlowNodeData = { label: string; kind: string; toolId?: string };
type FlowNode = Node<FlowNodeData>;
type ToolPaletteEntry = {
  id: string;
  label: string;
  type: string;
  toolId?: string;
  outputs?: Contract;
};
type WorkflowCanvasProps = {
  graph: WorkflowDefinition;
  onSave: (graph: WorkflowDefinition) => void;
  saving: boolean;
};

const nodePalette: ToolPaletteEntry[] = [
  {
    id: "get_open_orders",
    label: "Get open orders",
    type: "tool",
    toolId: "get_open_orders@1.0.0",
    outputs: {
      type: "object",
      properties: { orders: { type: "array" } },
      required: ["orders"],
    },
  },
  {
    id: "get_machine_capacity",
    label: "Get machine capacity",
    type: "tool",
    toolId: "get_machine_capacity@1.0.0",
    outputs: {
      type: "object",
      properties: {
        machines: { type: "array" },
        materials: { type: "array" },
      },
      required: ["machines", "materials"],
    },
  },
];

function mapGraphNodes(graph: WorkflowDefinition): FlowNode[] {
  return graph.nodes.map((node, index) => ({
    id: node.id,
    type: "default",
    position: { x: 80 + (index % 3) * 280, y: 50 + Math.floor(index / 3) * 190 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      label: node.id.replaceAll("_", " "),
      kind: node.type,
      toolId: node.tool_id,
    },
  }));
}

function mapGraphEdges(graph: WorkflowDefinition): Edge[] {
  return graph.edges.map((edge, index) => ({
    id: `${edge.from}-${edge.to}-${index}`,
    source: edge.from,
    target: edge.to,
    type: "smoothstep",
  }));
}

export default function WorkflowCanvas({
  graph,
  onSave,
  saving,
}: WorkflowCanvasProps) {
  const initialNodes = useMemo(() => mapGraphNodes(graph), [graph]);
  const initialEdges = useMemo(() => mapGraphEdges(graph), [graph]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(mapGraphNodes(graph));
    setEdges(mapGraphEdges(graph));
  }, [graph, setEdges, setNodes]);

  const nodeContracts = useMemo(
    () => new Map(graph.nodes.map((node) => [node.id, node])),
    [graph.nodes],
  );

  const connect = (connection: Connection) => {
    if (connection.source && connection.target && connection.source !== connection.target) {
      setEdges((current) => addEdge({ ...connection, type: "smoothstep" }, current));
    }
  };

  const addTool = (tool: ToolPaletteEntry) => {
    const id = `${tool.id}_${Date.now().toString(36)}`;
    setNodes((current) => [
      ...current,
      {
        id,
        type: "default",
        position: {
          x: 120 + (current.length % 3) * 260,
          y: 240 + Math.floor(current.length / 3) * 170,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: { label: tool.label, kind: tool.type, toolId: tool.toolId },
      },
    ]);
    nodeContracts.set(id, {
      id,
      type: tool.type,
      ...(tool.toolId ? { tool_id: tool.toolId } : {}),
      inputs: { type: "object", properties: {}, required: [] },
      outputs: tool.outputs ?? { type: "object", properties: {}, required: [] },
    });
  };

  const saveGraph = () => {
    const contracts = new Map(nodeContracts);
    const savedNodes = nodes.map((node) => {
      const existing = contracts.get(node.id);
      return existing ?? {
        id: node.id,
        type: node.data.kind,
        ...(node.data.toolId ? { tool_id: node.data.toolId } : {}),
        inputs: { type: "object", properties: {}, required: [] },
        outputs: { type: "object", properties: {}, required: [] },
      };
    });
    onSave({
      nodes: savedNodes,
      edges: edges.map(({ source, target }) => ({ from: source, to: target })),
    });
  };

  return (
    <div>
      <Space wrap style={{ marginBottom: 12 }}>
        <Text strong>Template tool palette</Text>
        {nodePalette.map((tool) => (
          <Button key={tool.id} size="small" onClick={() => addTool(tool)}>
            + {tool.label}
          </Button>
        ))}
        <Button
          size="small"
          danger
          disabled={!nodes.some((node) => node.selected)}
          onClick={() => {
            const removed = new Set(nodes.filter((node) => node.selected).map((node) => node.id));
            setNodes((current) => current.filter((node) => !removed.has(node.id)));
            setEdges((current) =>
              current.filter(
                (edge) => !removed.has(edge.source) && !removed.has(edge.target),
              ),
            );
          }}
        >
          Remove selected node
        </Button>
        <Button type="primary" loading={saving} onClick={saveGraph}>
          Validate and save workflow
        </Button>
      </Space>
      <div style={{ height: 580, border: "1px solid #d9d9d9", borderRadius: 8 }}>
        {nodes.length ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={connect}
            fitView
            deleteKeyCode={["Backspace", "Delete"]}
            attributionPosition="bottom-left"
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <MiniMap />
            <Controls />
          </ReactFlow>
        ) : (
          <Empty description="Add a workflow node to begin" />
        )}
      </div>
      <Space wrap style={{ marginTop: 12 }}>
        {nodes.map((node) => (
          <Tag key={node.id} color={node.data.kind === "tool" ? "blue" : "default"}>
            {node.data.label}
          </Tag>
        ))}
      </Space>
      <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
        Drag nodes and connect typed ports. Connect data-tool nodes to the
        optimizer to supply their outputs. Saving runs the manifest contract
        validator and commits a new version. Local data tools currently read
        synthetic demo data; no external API write tool is available.
      </Text>
    </div>
  );
}
