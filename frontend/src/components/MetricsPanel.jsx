import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

async function fetchMetrics() {
  const res = await fetch('/api/metrics')
  if (!res.ok) throw new Error('Failed to fetch metrics')
  return res.json()
}

function MetricCard({ label, value, color, warning }) {
  return (
    <div className={`rounded-lg border ${color} p-5 ${warning ? 'ring-1 ring-red-500' : ''}`}>
      <p className="text-xs uppercase tracking-widest text-gray-500 dark:text-gray-400 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${warning ? 'text-red-500 dark:text-red-400' : 'text-gray-800 dark:text-gray-100'}`}>{value}</p>
    </div>
  )
}

function formatDuration(seconds) {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function AccuracyBar({ value }) {
  if (value == null) return <span className="text-gray-400 dark:text-gray-600">—</span>
  const pct = Math.min(Math.max(value, 0), 100)
  const color = pct < 70 ? '#ef4444' : pct < 85 ? '#f59e0b' : '#22c55e'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-3 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-lg font-bold text-gray-800 dark:text-gray-100 font-mono w-16 text-right">
        {pct.toFixed(1)}%
      </span>
    </div>
  )
}

export default function MetricsPanel({ lastEvent }) {
  const { data, refetch } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 10000,
  })

  useEffect(() => {
    if (lastEvent) refetch()
  }, [lastEvent, refetch])

  const m = data ?? {
    active_agents: 0,
    total_agents: 0,
    total_tasks: 0,
    flagged_agents: 0,
    error_rate: 0,
    avg_accuracy: null,
    avg_duration_seconds: null,
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      {m.flagged_agents > 0 && (
        <div className="rounded-lg border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 px-5 py-3 flex items-center gap-3">
          <span className="text-red-500 dark:text-red-400 text-xl">⚑</span>
          <div>
            <p className="text-red-600 dark:text-red-300 font-semibold text-sm">
              {m.flagged_agents} agent{m.flagged_agents > 1 ? 's' : ''} flagged for termination
            </p>
            <p className="text-red-400 dark:text-red-600 text-xs">Accuracy dropped below 70% threshold</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Active Agents"
          value={m.active_agents}
          color="border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950"
        />
        <MetricCard
          label="Total Agents"
          value={m.total_agents}
          color="border-blue-300 dark:border-blue-800 bg-blue-50 dark:bg-blue-950"
        />
        <MetricCard
          label="Flagged"
          value={m.flagged_agents}
          color="border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950"
          warning={m.flagged_agents > 0}
        />
        <MetricCard
          label="Error Rate"
          value={`${(m.error_rate * 100).toFixed(1)}%`}
          color="border-purple-300 dark:border-purple-800 bg-purple-50 dark:bg-purple-950"
        />
      </div>

      <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-gray-500 dark:text-gray-400 mb-3">
            Average Accuracy
          </p>
          <AccuracyBar value={m.avg_accuracy} />
          {m.avg_accuracy != null && m.avg_accuracy < 70 && (
            <p className="text-red-500 dark:text-red-400 text-xs mt-2">
              ⚠ Fleet-wide accuracy is below the 70% threshold
            </p>
          )}
        </div>

        <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
          <p className="text-xs uppercase tracking-widest text-gray-500 dark:text-gray-400 mb-1">
            Avg Completion Time
          </p>
          <p className="text-2xl font-bold text-gray-800 dark:text-gray-100">
            {formatDuration(m.avg_duration_seconds)}
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-600 mt-1">for completed agents</p>
        </div>

        <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
          <p className="text-xs uppercase tracking-widest text-gray-500 dark:text-gray-400 mb-1">Total Tasks</p>
          <p className="text-2xl font-bold text-gray-800 dark:text-gray-100">{m.total_tasks}</p>
        </div>
      </div>
    </div>
  )
}
