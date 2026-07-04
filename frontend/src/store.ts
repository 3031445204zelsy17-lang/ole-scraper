import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Msg = { role: 'user' | 'assistant'; text: string }
type Session = { id: string; title: string; msgs: Msg[] }

type Store = {
  sessions: Record<string, Session>
  currentId: string
  streaming: string
  thinking: string[]
  newSession: () => void
  switchTo: (id: string) => void
  deleteSession: (id: string) => void
  appendUser: (text: string) => void
  appendDelta: (delta: string) => void
  finalize: (text: string) => void
  addThinking: (text: string) => void
}

const newId = () => `s_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`

export const useStore = create<Store>()(
  persist(
    (set, get) => ({
      sessions: {},
      currentId: '',
      streaming: '',
      thinking: [],
      newSession: () => {
        const id = newId()
        set((st) => ({
          sessions: { ...st.sessions, [id]: { id, title: '新对话', msgs: [] } },
          currentId: id,
          streaming: '',
          thinking: [],
        }))
      },
      switchTo: (id) => set({ currentId: id, streaming: '', thinking: [] }),
      deleteSession: (id) =>
        set((st) => {
          const sessions = { ...st.sessions }
          delete sessions[id]
          const ids = Object.keys(sessions)
          return {
            sessions,
            currentId: st.currentId === id ? ids[ids.length - 1] || '' : st.currentId,
          }
        }),
      appendUser: (text) => {
        const { currentId, sessions } = get()
        if (!sessions[currentId]) return
        set((st) => ({
          sessions: {
            ...st.sessions,
            [currentId]: {
              ...st.sessions[currentId],
              title: st.sessions[currentId].msgs.length === 0 ? text.slice(0, 24) : st.sessions[currentId].title,
              msgs: [...st.sessions[currentId].msgs, { role: 'user', text }],
            },
          },
        }))
      },
      appendDelta: (delta) => set((st) => ({ streaming: st.streaming + delta })),
      finalize: (text) => {
        const { currentId, sessions } = get()
        if (!sessions[currentId]) return
        set((st) => ({
          streaming: '',
          thinking: [],
          sessions: {
            ...st.sessions,
            [currentId]: {
              ...st.sessions[currentId],
              msgs: [...st.sessions[currentId].msgs, { role: 'assistant', text }],
            },
          },
        }))
      },
      addThinking: (text) => set((st) => ({ thinking: [...st.thinking, text] })),
    }),
    {
      name: 'ole-sessions',
      partialize: (s) => ({ sessions: s.sessions, currentId: s.currentId }) as unknown as Store,
    },
  ),
)

export function ensureSession() {
  const { sessions, currentId, newSession } = useStore.getState()
  if (Object.keys(sessions).length === 0 || !sessions[currentId]) newSession()
}
