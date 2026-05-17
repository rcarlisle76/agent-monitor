import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

const STATUS_STYLES = {
  running: 'bg-blue-900 text-blue-300',
  idle: 'bg-gray-800 text-gray-400',
  completed: 'bg-green-900 text-green-300',
  error: 'bg-red-900 text-red-300',
  terminated: 'bg-gray-900 text-gray-500',
}

const PAGE_SIZE = 50

async function fetchAgents() {
  const res = await fetch('/api/agents')
  if (!res.ok) throw new Error('Failed')
  return res.json()
}

async function fetchHistory(agentId) {
  const res = await fetch(`/api/agents/${encodeURIComponent(agentId)}/history`)
  if (!res.ok) throw new Error('Failed')
  return res.json()
}

export default function TaskHistory() {
  const [selectedAgent, setSelectedAgent] = useState('')
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(0)

  const { data: agents = [] } = useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  })

  const { data: history = [], isFetching } = useQuery({
    queryKey: ['history', selectedAgent],
    queryFn: () => fetchHistory(selectedAgent),
    enabled: !!selectedAgent,
  })

  const filtered = history.filter((r) => {
    if (!filter) return true
    const q = filter.toLowerCase()
    return (
      r.task?.toLowerCase().includes(q) ||
      r.status.toLowerCase().includes(q) ||
      JSON.stringify(r.metadata).toLowerCase().includes(q)
    )
  })

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  function handleAgentChange(e) {
    setSelectedAgent(e.target.value)
    setPage(0)
    setFilter('')
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-3 border-b border-gray-800 flex gap-3 flex-wrap">
        <select
          value={selectedAgent}
          onChange={handleAgentChange}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
        >
          <option value="">— Select agent —</option>
          {agents.map((a) => (
            <option key={a.agent_id} value={a.agent_id}>
              {a.agent_id}
            </option>
          ))}
        </select>

        {selectedAgent && (
          <input
            type="text"
            placeholder="Filter…"
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(0) }}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-indigo-500 flex-1 min-w-[160px]"
          />
        )}
      </div>

      {!selectedAgent ? (
        <p className="text-gray-600 text-sm mt-8 text-center">Select an agent to view history.</p>
      ) : isFetching ? (
        <p className="text-gray-600 text-sm mt-8 text-center">Loading…</p>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-900 border-b border-gray-800">
                <tr>
                  <th className="px-4 py-2 text-left text-xs text-gray-500 font-medium">Time</th>
                  <th className="px-4 py-2 text-left text-xs text-gray-500 font-medium">Status</th>
                  <th className="px-4 py-2 text-left text-xs text-gray-500 font-medium">Accuracy</th>
                  <th className="px-4 py-2 text-left text-xs text-gray-500 font-medium">Task</th>
                  <th className="px-4 py-2 text-left text-xs text-gray-500 font-medium">Metadata</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-gray-600 py-8">
                      No records found.
                    </td>
                  </tr>
                )}
                {pageRows.map((r) => (
                  <tr
                    key={r.id}
                    className={`border-b border-gray-800 hover:bg-gray-900 ${
                      r.accuracy != null && r.accuracy < 70 ? 'bg-red-950/20' : ''
                    }`}
                  >
                    <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                      {new Date(r.recorded_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLES[r.status] ?? STATUS_STYLES.idle}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs font-mono whitespace-nowrap">
                      {r.accuracy != null ? (
                        <span className={r.accuracy < 70 ? 'text-red-400 font-semibold' : 'text-gray-400'}>
                          {r.accuracy < 70 && '⚑ '}
                          {r.accuracy.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-300 max-w-xs truncate">
                      {r.task ?? <span className="italic text-gray-600">—</span>}
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs max-w-xs truncate font-mono">
                      {Object.keys(r.metadata).length > 0
                        ? JSON.stringify(r.metadata)
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="px-6 py-2 border-t border-gray-800 flex items-center gap-3 text-xs text-gray-500">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="disabled:opacity-30 hover:text-gray-200"
              >
                ← Prev
              </button>
              <span>
                Page {page + 1} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="disabled:opacity-30 hover:text-gray-200"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
