import { useQuery } from '@tanstack/react-query'
import dagre from 'dagre'
import { useEffect, useState } from 'react'
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

const STATUS_COLORS = {
  running: '#3b82f6',
  idle: '#6b7280',
  completed: '#22c55e',
  error: '#ef4444',
  terminated: '#374151',
}

function AgentNode({ data }) {
  const isTerminated = data.status === 'terminated'
  const color = isTerminated ? '#374151' : data.flagged ? '#ef4444' : (STATUS_COLORS[data.status] ?? '#6b7280')
  const accuracy = data.accuracy
  const isLR = data.direction === 'LR'
  const targetPos = isLR ? Position.Left : Position.Top
  const sourcePos = isLR ? Position.Right : Position.Bottom

  return (
    <div
      className={`rounded-lg border px-4 py-3 text-xs shadow-lg min-w-[160px] max-w-[220px] ${
        isTerminated ? 'bg-gray-950 opacity-50' : 'bg-gray-900'
      }`}
      style={{ borderColor: color, borderWidth: data.flagged && !isTerminated ? 2 : 1 }}
    >
      <Handle type="target" position={targetPos} style={{ background: color }} />
      <div className="flex items-center justify-between gap-2 mb-1">
        <p className={`font-bold truncate flex-1 ${isTerminated ? 'text-gray-500 line-through' : 'text-gray-100'}`}>
          {data.flagged && !isTerminated && <span className="text-red-400 mr-1">⚑</span>}
          {isTerminated && <span className="text-gray-500 mr-1">✕</span>}
          {data.label}
        </p>
        <span
          className="inline-block px-2 py-0.5 rounded text-white text-[10px] flex-shrink-0"
          style={{ background: color }}
        >
          {data.status}
        </span>
      </div>

      {data.replaces && (
        <p className="text-indigo-400 text-[10px] mb-1">↺ replacing {data.replaces}</p>
      )}

      {accuracy != null && !isTerminated && (
        <div className="flex items-center gap-1 mt-1">
          <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(accuracy, 100)}%`,
                background: accuracy < 70 ? '#ef4444' : accuracy < 85 ? '#f59e0b' : '#22c55e',
              }}
            />
          </div>
          <span
            className={`text-[10px] font-mono flex-shrink-0 ${
              accuracy < 70 ? 'text-red-400' : 'text-gray-400'
            }`}
          >
            {accuracy.toFixed(1)}%
          </span>
        </div>
      )}

      {data.flagged && !isTerminated && (
        <p className="text-red-400 text-[10px] font-semibold mt-1">⚠ Flagged for termination</p>
      )}

      {isTerminated && (
        <p className="text-gray-600 text-[10px] mt-1">Terminated by orchestrator</p>
      )}

      {data.task && !data.flagged && !isTerminated && (
        <p className="text-gray-400 mt-1 truncate text-[10px]">{data.task}</p>
      )}

      <Handle type="source" position={sourcePos} style={{ background: color }} />
    </div>
  )
}

const NODE_TYPES = { agentNode: AgentNode }
const NODE_WIDTH = 220
const NODE_HEIGHT = 90

function layoutNodes(agents, direction = 'LR') {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 120 })

  const nodes = agents.map((a) => ({
    id: a.agent_id,
    type: 'agentNode',
    data: {
      label: a.agent_id,
      status: a.status,
      task: a.current_task,
      accuracy: a.current_accuracy,
      flagged: a.flagged,
      replaces: a.replaces ?? null,
      direction,
    },
    position: { x: 0, y: 0 },
  }))

  const edges = agents
    .filter((a) => a.parent_id)
    .map((a) => ({
      id: `${a.parent_id}-${a.agent_id}`,
      source: a.parent_id,
      target: a.agent_id,
      style: { stroke: a.flagged ? '#7f1d1d' : '#4b5563' },
    }))

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  edges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)

  const laid = nodes.map((n) => {
    const pos = g.node(n.id)
    return { ...n, position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 } }
  })

  return { nodes: laid, edges }
}

async function fetchAgents() {
  const res = await fetch('/api/agents')
  if (!res.ok) throw new Error('Failed to fetch agents')
  return res.json()
}

export default function HierarchyTree({ lastEvent }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [direction, setDirection] = useState('LR')

  const { data: agents, refetch } = useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  })

  useEffect(() => {
    if (lastEvent) refetch()
  }, [lastEvent, refetch])

  useEffect(() => {
    if (!agents?.length) return
    const { nodes: n, edges: e } = layoutNodes(agents, direction)
    setNodes(n)
    setEdges(e)
  }, [agents, direction, setNodes, setEdges])

  const flaggedCount = agents?.filter((a) => a.flagged).length ?? 0

  return (
    <div className="h-full w-full flex flex-col">
      <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
        {flaggedCount > 0 ? (
          <div className="flex items-center gap-2">
            <span className="text-red-500 dark:text-red-400 text-sm font-semibold">
              ⚑ {flaggedCount} agent{flaggedCount > 1 ? 's' : ''} flagged for termination
            </span>
            <span className="text-red-400 dark:text-red-600 text-xs">(accuracy below 70%)</span>
          </div>
        ) : <div />}
        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => setDirection('LR')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              direction === 'LR' ? 'bg-white dark:bg-gray-600 text-gray-800 dark:text-white shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
            title="Horizontal layout (orchestrator left, workers spread right)"
          >
            Horizontal
          </button>
          <button
            onClick={() => setDirection('TB')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              direction === 'TB' ? 'bg-white dark:bg-gray-600 text-gray-800 dark:text-white shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
            title="Vertical layout (orchestrator top, workers spread down)"
          >
            Vertical
          </button>
        </div>
      </div>
      {nodes.length === 0 ? (
        <p className="text-gray-400 dark:text-gray-600 text-sm mt-8 text-center">No agents reported yet…</p>
      ) : (
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            fitView
            colorMode="dark"
          >
            <Background color="#374151" gap={24} />
            <Controls />
            <MiniMap nodeColor={(n) => n.data?.flagged ? '#ef4444' : (STATUS_COLORS[n.data?.status] ?? '#6b7280')} />
          </ReactFlow>
        </div>
      )}
    </div>
  )
}
