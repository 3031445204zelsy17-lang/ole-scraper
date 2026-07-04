import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { useStore, ensureSession } from './store'
import { useChatWS } from './useChatWS'

const Md = ({ children }: { children: string }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    rehypePlugins={[rehypeHighlight]}
    components={{
      a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      ),
    }}
  >
    {children}
  </ReactMarkdown>
)

function App() {
  const [input, setInput] = useState('')
  const sessions = useStore((s) => s.sessions)
  const currentId = useStore((s) => s.currentId)
  const streaming = useStore((s) => s.streaming)
  const thinking = useStore((s) => s.thinking)
  const { send, newSession, switchTo } = useChatWS()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    ensureSession()
  }, [])
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [currentId, streaming, thinking])

  const cur = sessions[currentId]
  const sendNew = () => {
    const t = input.trim()
    if (!t) return
    send(t)
    setInput('')
  }

  return (
    <div className="h-screen flex bg-[#1f1f1e] text-[#ececec]">
      <aside className="w-60 border-r border-[#2f2f2d] flex flex-col">
        <button
          onClick={newSession}
          className="m-3 px-3 py-2 bg-[#d97757] hover:bg-[#c26844] rounded-lg text-white text-sm font-medium"
        >
          + 新对话
        </button>
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {Object.values(sessions)
            .slice()
            .reverse()
            .map((s) => (
              <div
                key={s.id}
                onClick={() => switchTo(s.id)}
                className={`group flex items-center px-3 py-2 rounded-lg cursor-pointer text-sm ${
                  s.id === currentId ? 'bg-[#303030]' : 'hover:bg-[#2a2a28]'
                }`}
              >
                <span className="flex-1 truncate">{s.title || '新对话'}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    useStore.getState().deleteSession(s.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 text-[#666] hover:text-[#d97757] ml-2 text-lg leading-none"
                >
                  ×
                </button>
              </div>
            ))}
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="px-6 py-3 border-b border-[#2f2f2d]">
          <span className="text-[#d97757] font-semibold">OLE Agent</span>
          <span className="text-[#888] ml-2 text-sm">HKMU 学习助手</span>
        </header>

        <main ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {(!cur || cur.msgs.length === 0) && !streaming && !thinking.length && (
              <div className="text-center text-[#777] mt-24">
                <h1 className="text-3xl mb-3 text-[#ececec]">OLE Agent</h1>
                <p className="text-sm">问我课程、作业、成绩,或「根据课件,Tutorial 6 讲了哪些分布?」</p>
              </div>
            )}

            {cur?.msgs.map((m, i) =>
              m.role === 'user' ? (
                <div key={i} className="flex justify-end">
                  <div className="bg-[#303030] rounded-2xl px-4 py-2 max-w-[80%] whitespace-pre-wrap">{m.text}</div>
                </div>
              ) : (
                <div key={i} className="prose-chat">
                  <Md>{m.text}</Md>
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
                <Md>{streaming}</Md>
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
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendNew()
                }
              }}
              placeholder="输入消息…(Shift+Enter 换行)"
              rows={1}
              className="flex-1 bg-[#2a2a28] text-[#ececec] rounded-xl px-4 py-3 resize-none outline-none placeholder-[#666] focus:ring-1 focus:ring-[#d97757] max-h-40"
            />
            <button onClick={sendNew} className="bg-[#d97757] hover:bg-[#c26844] text-white rounded-xl px-5 py-3 font-medium whitespace-nowrap">
              发送
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

export default App
