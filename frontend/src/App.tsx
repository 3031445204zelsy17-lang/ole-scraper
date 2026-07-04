import { useEffect, useRef, useState } from 'react'

type Msg = { role: 'user' | 'assistant'; text: string }

function App() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      if (d.type === 'delta') setStreaming((s) => s + d.text)
      else if (d.type === 'final') {
        setMsgs((m) => [...m, { role: 'assistant', text: d.text }])
        setStreaming('')
      }
      // thinking 暂不渲染(骨架;P3.5-2 加)
    }
    return () => ws.close()
  }, [])

  const send = () => {
    const t = input.trim()
    if (!t || !wsRef.current) return
    setMsgs((m) => [...m, { role: 'user', text: t }])
    wsRef.current.send(t)
    setInput('')
  }

  return (
    <div style={{ maxWidth: 768, margin: '0 auto', padding: 16, display: 'flex', flexDirection: 'column', height: '100vh', boxSizing: 'border-box' }}>
      <h1 style={{ fontSize: 20, margin: '8px 0' }}>OLE Agent（骨架 · Phase 3.5-1）</h1>
      <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ margin: '4px 0', textAlign: m.role === 'user' ? 'right' : 'left' }}>
            <span style={{
              background: m.role === 'user' ? '#2563eb' : '#e5e7eb',
              color: m.role === 'user' ? '#fff' : '#000',
              padding: '4px 8px', borderRadius: 6, whiteSpace: 'pre-wrap', display: 'inline-block', maxWidth: '80%',
            }}>{m.text}</span>
          </div>
        ))}
        {streaming && (
          <div style={{ margin: '4px 0', textAlign: 'left' }}>
            <span style={{ background: '#e5e7eb', padding: '4px 8px', borderRadius: 6, whiteSpace: 'pre-wrap', display: 'inline-block', maxWidth: '80%' }}>{streaming}▋</span>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') send() }}
          placeholder="输入消息..."
          style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #ddd' }}
        />
        <button onClick={send} style={{ padding: '8px 16px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>发送</button>
      </div>
    </div>
  )
}

export default App
