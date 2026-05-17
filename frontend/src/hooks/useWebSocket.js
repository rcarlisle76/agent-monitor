import { useCallback, useEffect, useRef, useState } from 'react'

export function useWebSocket() {
  const [lastEvent, setLastEvent] = useState(null)
  const [connectionStatus, setConnectionStatus] = useState('connecting')
  const wsRef = useRef(null)
  const retryDelay = useRef(1000)
  const unmounted = useRef(false)

  const connect = useCallback(() => {
    if (unmounted.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws`)
    wsRef.current = ws

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)

    ws.onopen = () => {
      if (unmounted.current) return
      setConnectionStatus('connected')
      retryDelay.current = 1000
    }

    ws.onmessage = (e) => {
      if (unmounted.current) return
      try {
        setLastEvent(JSON.parse(e.data))
      } catch {
        // ignore non-JSON messages (e.g. pong)
      }
    }

    ws.onclose = () => {
      clearInterval(pingInterval)
      if (unmounted.current) return
      setConnectionStatus('reconnecting')
      setTimeout(connect, retryDelay.current)
      retryDelay.current = Math.min(retryDelay.current * 2, 30000)
    }

    ws.onerror = () => ws.close()

    return () => {
      clearInterval(pingInterval)
      ws.close()
    }
  }, [])

  useEffect(() => {
    unmounted.current = false
    const cleanup = connect()
    return () => {
      unmounted.current = true
      cleanup?.()
    }
  }, [connect])

  return { lastEvent, connectionStatus }
}
