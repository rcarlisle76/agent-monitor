import { useEffect, useRef, useState } from 'react'

const STATUS_STYLES = {
  running: 'bg-blue-900 text-blue-300 border-blue-700',
  idle: 'bg-gray-800 text-gray-400 border-gray-600',
  completed: 'bg-green-900 text-green-300 border-green-700',
  error: 'bg-red-900 text-red-300 border-red-700',
  terminated: 'bg-gray-900 text-gray-500 border-gray-700',
}

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString() } catch { return iso }
}

function AccuracyBadge({ accuracy }) {
  if (accuracy == null) return null
  const low = accuracy < 70
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded border flex-shrink-0 font-mono ${
        low
          ? 'bg-red-900 text-red-300 border-red-600'
          : 'bg-gray-800 text-gray-400 border-gray-600'
      }`}
    >
      {accuracy.toFixed(1)}%
    </span>
  )
}

export default function LiveFeed({ lastEvent }) {
  const [events, setEvents] = useState([])
  const seqRef = useRef(0)

  useEffect(() => {
    if (!lastEvent) return
    const keyed = { ...lastEvent, _seq: seqRef.current++ }
    setEvents((prev) => [keyed, ...prev].slice(0, 500))
  }, [lastEvent])

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-2 border-b border-gray-800 flex items-center justify-between">
        <span className="text-xs text-gray-500">{events.length} events</span>
        <button
          onClick={() => setEvents([])}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
        {events.length === 0 && (
          <p className="text-gray-600 text-sm mt-8 text-center">Waiting for agent events…</p>
        )}
        {events.map((evt) => (
          <div
            key={evt._seq}
            className={`flex items-start gap-3 py-2 border-b last:border-0 ${
              evt.status === 'terminated'
                ? 'border-gray-800 opacity-60'
                : evt.flagged
                ? 'border-red-900 bg-red-950/30'
                : 'border-gray-800'
            }`}
          >
            <span className="text-xs text-gray-600 w-20 flex-shrink-0 pt-0.5">
              {formatTime(evt.timestamp)}
            </span>
            <span className={`text-sm font-semibold w-32 flex-shrink-0 truncate ${evt.status === 'terminated' ? 'text-gray-500 line-through' : 'text-gray-200'}`}>
              {evt.flagged && evt.status !== 'terminated' && <span className="text-red-400 mr-1">⚑</span>}
              {evt.status === 'terminated' && <span className="text-gray-500 mr-1">✕</span>}
              {evt.agent_id}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded border flex-shrink-0 ${
                STATUS_STYLES[evt.status] ?? STATUS_STYLES.idle
              }`}
            >
              {evt.status}
            </span>
            <AccuracyBadge accuracy={evt.accuracy} />
            <span className="text-sm text-gray-400 truncate flex-1">
              {evt.task ?? <span className="italic text-gray-600">no task</span>}
            </span>
            {evt.flagged && evt.status !== 'terminated' && (
              <span className="text-xs text-red-400 flex-shrink-0 font-semibold">FLAGGED</span>
            )}
            {evt.status === 'terminated' && (
              <span className="text-xs text-gray-500 flex-shrink-0 font-semibold">TERMINATED</span>
            )}
            {evt.metadata?.replaces && (
              <span className="text-xs text-indigo-400 flex-shrink-0">
                ↺ replacing {evt.metadata.replaces}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
