import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'

type Msg = { role: 'user' | 'assistant'; text: string }

function App() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState('')
  const [thinking, setThinking] = useState<string[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws`)
    wsRef.current = ws
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      if (d.type === 'delta') setStreaming((s) => s + d.text)
      else if (d.type === 'thinking') setThinking((t) => [...t, d.text])
      else if (d.type === 'final') {
        setMsgs((m) => [...m, { role: 'assistant', text: d.text }])
        setStreaming('')
        setThinking([])
      }
    }
    return () => ws.close()
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [msgs, streaming, thinking])

  const send = () => {
    const t = input.trim()
    if (!t || !wsRef.current) return
    setMsgs((m) => [...m, { role: 'user', text: t }])
    wsRef.current.send(t)
    setInput('')
  }

  return (
    <div className="h-screen flex flex-col bg-[#1f1f1e] text-[#ececec]">
      <header className="px-6 py-3 border-b border-[#2f2f2d]">
        <span className="text-[#d97757] font-semibold">OLE Agent</span>
        <span className="text-[#888] ml-2 text-sm">HKMU 学习助手</span>
      </header>

      <main ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {msgs.length === 0 && !streaming && !thinking.length && (
            <div className="text-center text-[#777] mt-24">
              <h1 className="text-3xl mb-3 text-[#ececec]">OLE Agent</h1>
              <p className="text-sm">问我课程、作业、成绩,或「根据课件,Tutorial 6 讲了哪些分布?」</p>
            </div>
          )}

          {msgs.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="flex justify-end">
                <div className="bg-[#303030] rounded-2xl px-4 py-2 max-w-[80%] whitespace-pre-wrap">{m.text}</div>
              </div>
            ) : (
              <div key={i} className="prose-chat">
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{m.text}</ReactMarkdown>
              </div>
            ),
          )}

          {thinking.length > 0 && (
            <div className="text-xs text-[#777] space-y-1 border-l-2 border-[#444] pl-3">
              {thinking.map((t, i) => <div key={i}>{t}</div>)}
            </div>
          )}

          {streaming && (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{streaming}</ReactMarkdown>
              <span className="inline-block w-2 h-4 bg-[#d97757] animate-pulse align-middle ml-0.5" />
            </div>
          )}
        </div>
      </main>

      <footer className="border-t border-[#2f2f2d] px-4 py-4">
        <div className="max-w-3xl mx-auto flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="输入消息…(Shift+Enter 换行)"
            rows={1}
            className="flex-1 bg-[#2a2a28] text-[#ececec] rounded-xl px-4 py-3 resize-none outline-none placeholder-[#666] focus:ring-1 focus:ring-[#d97757] max-h-40"
          />
          <button onClick={send} className="bg-[#d97757] hover:bg-[#c26844] text-white rounded-xl px-5 py-3 font-medium whitespace-nowrap">发送</button>
        </div>
      </footer>
    </div>
  )
}

export default App
