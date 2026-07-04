import { useEffect, useRef } from 'react'
import { useStore } from './store'

export function useChatWS() {
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      const st = useStore.getState()
      if (d.type === 'delta') st.appendDelta(d.text)
      else if (d.type === 'thinking') st.addThinking(d.text)
      else if (d.type === 'final') st.finalize(d.text)
    }
    return () => ws.close()
  }, [])

  const restoreCurrent = () => {
    const { sessions, currentId } = useStore.getState()
    const history = (sessions[currentId]?.msgs || []).map((m) => ({ role: m.role, content: m.text }))
    wsRef.current?.send('__RESTORE__' + JSON.stringify(history))
  }

  const send = (text: string) => {
    useStore.getState().appendUser(text)
    wsRef.current?.send(text)
  }

  const newSession = () => {
    useStore.getState().newSession()
    wsRef.current?.send('__RESTORE__[]')
  }

  const switchTo = (id: string) => {
    useStore.getState().switchTo(id)
    restoreCurrent()
  }

  return { send, newSession, switchTo }
}
