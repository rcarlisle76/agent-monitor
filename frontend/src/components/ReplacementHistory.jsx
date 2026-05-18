import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

async function fetchChains() {
  const res = await fetch('/api/replacement-chains')
  if (!res.ok) throw new Error('Failed to fetch replacement chains')
  return res.json()
}

const STATUS_COLORS = {
  running:    { bg: 'bg-blue-100 dark:bg-blue-900',   text: 'text-blue-700 dark:text-blue-300',   border: 'border-blue-300 dark:border-blue-700'   },
  idle:       { bg: 'bg-gray-100 dark:bg-gray-800',   text: 'text-gray-500 dark:text-gray-400',   border: 'border-gray-300 dark:border-gray-600'   },
  completed:  { bg: 'bg-green-100 dark:bg-green-900', text: 'text-green-700 dark:text-green-300', border: 'border-green-300 dark:border-green-700' },
  error:      { bg: 'bg-red-100 dark:bg-red-900',     text: 'text-red-700 dark:text-red-300',     border: 'border-red-300 dark:border-red-700'     },
  terminated: { bg: 'bg-gray-50 dark:bg-gray-900',    text: 'text-gray-400 dark:text-gray-500',   border: 'border-gray-200 dark:border-gray-700'   },
}

function fmt(iso) {
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

function AccuracyPill({ value }) {
  if (value == null) return <span className="text-gray-400 dark:text-gray-600 text-xs">no accuracy data</span>
  const low = value < 70
  return (
    <span className={`font-mono text-xs font-semibold ${low ? 'text-red-500 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`}>
      {low && '⚑ '}{value.toFixed(1)}%
    </span>
  )
}

function ChainNode({ member, isLast, replacedBy }) {
  const s = STATUS_COLORS[member.status] ?? STATUS_COLORS.idle
  const isTerminated = member.status === 'terminated'

  return (
    <div className="flex flex-col items-stretch">
      <div className={`rounded-lg border ${s.border} p-4 ${isTerminated ? 'opacity-60' : ''}`}>
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div className="min-w-0">
            <p className={`font-bold text-sm truncate ${isTerminated ? 'text-gray-400 dark:text-gray-500 line-through' : 'text-gray-800 dark:text-gray-100'}`}>
              {isTerminated && <span className="mr-1 no-underline" style={{textDecoration:'none'}}>✕ </span>}
              {member.agent_id}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-600 mt-0.5">First seen: {fmt(member.first_seen)}</p>
            {isTerminated && (
              <p className="text-xs text-gray-400 dark:text-gray-600">Terminated: {fmt(member.last_updated)}</p>
            )}
          </div>
          <span className={`text-xs px-2 py-0.5 rounded ${s.bg} ${s.text} flex-shrink-0`}>
            {member.status}
          </span>
        </div>

        <div className="mt-3 flex flex-wrap gap-4 text-xs">
          <div>
            <p className="text-gray-400 dark:text-gray-600 mb-0.5 uppercase tracking-wide text-[10px]">
              {isTerminated ? 'Accuracy at termination' : 'Last accuracy'}
            </p>
            <AccuracyPill value={member.last_accuracy ?? member.current_accuracy} />
          </div>
          {isTerminated && replacedBy && (
            <div>
              <p className="text-gray-400 dark:text-gray-600 mb-0.5 uppercase tracking-wide text-[10px]">Replaced by</p>
              <span className="text-indigo-600 dark:text-indigo-400 font-semibold">{replacedBy}</span>
            </div>
          )}
          {member.flagged && !isTerminated && (
            <div>
              <p className="text-gray-400 dark:text-gray-600 mb-0.5 uppercase tracking-wide text-[10px]">Flag</p>
              <span className="text-red-500 dark:text-red-400 font-semibold text-xs">⚑ Below threshold</span>
            </div>
          )}
        </div>
      </div>

      {!isLast && (
        <div className="flex flex-col items-center py-1">
          <div className="h-3 w-px bg-gray-300 dark:bg-gray-700" />
          <span className="text-indigo-500 dark:text-indigo-400 text-base leading-none">↓</span>
          <div className="h-3 w-px bg-gray-300 dark:bg-gray-700" />
        </div>
      )}
    </div>
  )
}

function ChainCard({ chain }) {
  const replacements = chain.replacements
  const current = chain.current

  const headerColor =
    current.status === 'terminated' ? 'border-gray-200 dark:border-gray-700'
    : current.flagged ? 'border-red-300 dark:border-red-800'
    : 'border-indigo-300 dark:border-indigo-800'

  return (
    <div className={`rounded-xl border ${headerColor} bg-white dark:bg-gray-900 overflow-hidden`}>
      <div className="px-5 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-gray-800 dark:text-gray-200 font-bold text-sm">{chain.base_id}</span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {replacements} replacement{replacements !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 dark:text-gray-500">Current:</span>
          <span className={`text-xs font-semibold ${
            current.status === 'running' ? 'text-blue-600 dark:text-blue-400'
            : current.status === 'completed' ? 'text-green-600 dark:text-green-400'
            : 'text-gray-500 dark:text-gray-400'
          }`}>
            {current.agent_id}
          </span>
        </div>
      </div>

      <div className="p-5 flex flex-col">
        {chain.chain.map((member, i) => (
          <ChainNode
            key={member.agent_id}
            member={member}
            isLast={i === chain.chain.length - 1}
            replacedBy={chain.chain[i + 1]?.agent_id}
          />
        ))}
      </div>
    </div>
  )
}

export default function ReplacementHistory({ lastEvent }) {
  const { data: chains = [], refetch, isFetching } = useQuery({
    queryKey: ['replacement-chains'],
    queryFn: fetchChains,
  })

  useEffect(() => {
    if (lastEvent?.status === 'terminated' || lastEvent?.replaces) {
      refetch()
    }
  }, [lastEvent, refetch])

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-2 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {chains.length} chain{chains.length !== 1 ? 's' : ''} with replacements
        </span>
        <button
          onClick={() => refetch()}
          className="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
        >
          {isFetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {chains.length === 0 && !isFetching && (
          <div className="text-center mt-16">
            <p className="text-gray-400 dark:text-gray-500 text-sm">No replacements yet.</p>
            <p className="text-gray-300 dark:text-gray-600 text-xs mt-1">
              Agents will appear here when they are terminated and replaced.
            </p>
          </div>
        )}
        {chains.map((chain) => (
          <ChainCard key={chain.base_id} chain={chain} />
        ))}
      </div>
    </div>
  )
}
