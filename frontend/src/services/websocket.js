let ws = null
const listeners = new Map()

export function connectWebSocket(token, onOpen) {
  if (ws && ws.readyState === WebSocket.OPEN) return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  ws = new WebSocket(`${protocol}//${host}/ws?token=${token}`)

  ws.onopen = () => {
    onOpen?.()
    // Ping every 25 seconds to keep connection alive
    ws._pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25_000)
  }

  ws.onmessage = (event) => {
    if (event.data === 'pong') return
    try {
      const { type, data } = JSON.parse(event.data)
      listeners.get(type)?.forEach((cb) => cb(data))
      listeners.get('*')?.forEach((cb) => cb({ type, data }))
    } catch {}
  }

  ws.onclose = () => {
    clearInterval(ws._pingInterval)
    // Reconnect after 5 seconds
    setTimeout(() => {
      if (localStorage.getItem('access_token')) connectWebSocket(token, onOpen)
    }, 5_000)
  }
}

export function disconnectWebSocket() {
  if (ws) {
    clearInterval(ws._pingInterval)
    ws.close()
    ws = null
  }
  listeners.clear()
}

export function onWsEvent(eventType, callback) {
  if (!listeners.has(eventType)) listeners.set(eventType, new Set())
  listeners.get(eventType).add(callback)
  return () => listeners.get(eventType)?.delete(callback)
}
