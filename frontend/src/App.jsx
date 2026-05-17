import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import HierarchyTree from './components/HierarchyTree'
import LiveFeed from './components/LiveFeed'
import MetricsPanel from './components/MetricsPanel'
import ReplacementHistory from './components/ReplacementHistory'
import TaskHistory from './components/TaskHistory'
import { useWebSocket } from './hooks/useWebSocket'

const TABS = [
  { id: 'feed', label: 'Live Feed' },
  { id: 'tree', label: 'Hierarchy' },
  { id: 'history', label: 'History' },
  { id: 'replacements', label: 'Replacements' },
  { id: 'metrics', label: 'Metrics' },
]

const STATUS_DOT = {
  connected: 'bg-green-400',
  reconnecting: 'bg-yellow-400',
  connecting: 'bg-gray-400',
}

export default function App() {
  const [activeTab, setActiveTab] = useState('feed')
  const [clearing, setClearing] = useState(false)
  const { lastEvent, connectionStatus } = useWebSocket()
  const queryClient = useQueryClient()

  async function handleClear() {
    if (!window.confirm('Clear all agents and task history? This cannot be undone.')) return
    setClearing(true)
    try {
      await fetch('/api/agents', { method: 'DELETE' })
      queryClient.invalidateQueries()
    } finally {
      setClearing(false)
    }
  }

  const { data: chains = [] } = useQuery({
    queryKey: ['replacement-chains'],
    queryFn: () => fetch('/api/replacement-chains').then(r => r.json()),
    refetchInterval: 15000,
  })

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 font-mono">
      {/* Sidebar */}
      <aside className="w-48 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-800">
          <h1 className="text-sm font-bold tracking-widest text-indigo-400 uppercase">
            Agent Monitor
          </h1>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full text-left px-3 py-2 rounded text-sm transition-colors flex items-center justify-between ${
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`}
            >
              <span>{tab.label}</span>
              {tab.id === 'replacements' && chains.length > 0 && (
                <span className={`text-xs rounded-full px-1.5 py-0.5 font-mono ${
                  activeTab === tab.id ? 'bg-indigo-500 text-white' : 'bg-gray-700 text-gray-300'
                }`}>
                  {chains.length}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="px-4 py-3 border-t border-gray-800 flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${STATUS_DOT[connectionStatus]}`} />
          <span className="text-xs text-gray-500 capitalize">{connectionStatus}</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <header className="px-6 py-4 border-b border-gray-800 bg-gray-900 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-200">
            {TABS.find((t) => t.id === activeTab)?.label}
          </h2>
          <button
            onClick={handleClear}
            disabled={clearing}
            className="px-3 py-1.5 rounded text-xs font-medium bg-gray-800 text-gray-400 hover:bg-red-950 hover:text-red-400 border border-gray-700 hover:border-red-800 transition-colors disabled:opacity-50"
          >
            {clearing ? 'Clearing…' : 'Clear All'}
          </button>
        </header>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'feed' && <LiveFeed lastEvent={lastEvent} />}
          {activeTab === 'tree' && <HierarchyTree lastEvent={lastEvent} />}
          {activeTab === 'history' && <TaskHistory />}
          {activeTab === 'replacements' && <ReplacementHistory lastEvent={lastEvent} />}
          {activeTab === 'metrics' && <MetricsPanel lastEvent={lastEvent} />}
        </div>
      </main>
    </div>
  )
}
