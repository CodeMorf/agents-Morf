/** ChatGPT / Grok style client workspace — providers stay server-side. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, MessageSquarePlus, Moon, Send, Sun, Trash2 } from 'lucide-react'
import { Agent, ChatResponse, api } from './api'

export type ConversationSummary = {
  id: string
  agent_id?: string
  title: string
  status: string
  updated_at: string
}

export type ChatMessage = {
  id?: string
  role: string
  content: string
  model?: string
  provider?: string
}

type Theme = 'dark' | 'light'

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('am_theme')
    return saved === 'light' || saved === 'dark' ? saved : 'dark'
  })
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('am_theme', theme)
  }, [theme])
  return [theme, () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))]
}

export function ChatWorkspace() {
  const queryClient = useQueryClient()
  const [theme, toggleTheme] = useTheme()
  const { data: agents = [] } = useQuery({
    queryKey: ['agents'],
    queryFn: () => api<Agent[]>('/agents'),
  })
  const { data: conversations = [], refetch: refetchConvos } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => api<ConversationSummary[]>('/conversations'),
  })
  const [agentId, setAgentId] = useState('')
  const [conversationId, setConversationId] = useState<string>()
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [meta, setMeta] = useState<{ provider?: string; model?: string; latency?: number }>({})
  const bottomRef = useRef<HTMLDivElement>(null)
  const selectedAgent = useMemo(
    () => agents.find(a => a.id === agentId) || agents[0],
    [agents, agentId],
  )

  useEffect(() => {
    if (!agentId && agents[0]) setAgentId(agents[0].id)
  }, [agents, agentId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, meta])

  const loadMessages = useMutation({
    mutationFn: (id: string) =>
      api<ChatMessage[]>(`/conversations/${id}/messages`),
    onSuccess: (rows, id) => {
      setConversationId(id)
      setHistory(
        rows
          .filter(r => r.role === 'user' || r.role === 'assistant')
          .map(r => ({ role: r.role, content: r.content || '', id: r.id, model: r.model })),
      )
    },
  })

  const send = useMutation({
    mutationFn: async () => {
      const messages = [...history, { role: 'user', content: input }]
      return api<ChatResponse>('/chat/completions', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: selectedAgent?.id || agentId || undefined,
          conversation_id: conversationId,
          end_user_id: 'dashboard-user',
          messages: messages.map(m => ({ role: m.role, content: m.content })),
          stream: false,
          remember: true,
        }),
      })
    },
    onSuccess: result => {
      const answer = result.choices[0]?.message
      setHistory(h => [
        ...h,
        { role: 'user', content: input },
        {
          role: 'assistant',
          content:
            answer?.content ||
            (answer?.tool_calls?.length
              ? `[Tool: ${answer.tool_calls.map(t => t.name).join(', ')}]`
              : ''),
        },
      ])
      setConversationId(result.conversation_id)
      setMeta({
        provider: result.provider,
        model: result.model,
        latency: result.latency_ms,
      })
      setInput('')
      refetchConvos()
      queryClient.invalidateQueries({ queryKey: ['usage'] })
    },
  })

  function newChat() {
    setConversationId(undefined)
    setHistory([])
    setMeta({})
    setInput('')
  }

  return (
    <div className="gpt-shell">
      <aside className="gpt-sidebar">
        <button type="button" className="primary compact gpt-new" onClick={newChat}>
          <MessageSquarePlus size={16} /> Nuevo chat
        </button>
        <div className="gpt-convo-list">
          {conversations.map(c => (
            <button
              type="button"
              key={c.id}
              className={conversationId === c.id ? 'gpt-convo active' : 'gpt-convo'}
              onClick={() => loadMessages.mutate(c.id)}
            >
              <span>{c.title || 'Conversación'}</span>
              <small>{new Date(c.updated_at).toLocaleString()}</small>
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="muted gpt-empty-side">Sin conversaciones aún</p>
          )}
        </div>
        <div className="gpt-side-foot">
          <button type="button" className="secondary compact" onClick={toggleTheme} title="Tema">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            {theme === 'dark' ? ' Modo claro' : ' Modo oscuro'}
          </button>
        </div>
      </aside>

      <section className="gpt-main">
        <header className="gpt-top">
          <div>
            <p className="eyebrow">CHAT</p>
            <h1>{selectedAgent?.name || 'Agents Morf'}</h1>
            <p className="muted">
              El modelo se elige en el backend (Groq). Tú solo conversas.
            </p>
          </div>
          <label className="gpt-agent-pick">
            Agente
            <select
              value={selectedAgent?.id || ''}
              onChange={e => {
                setAgentId(e.target.value)
                newChat()
              }}
            >
              {agents.map(a => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="gpt-messages">
          {history.length === 0 && (
            <div className="gpt-hero-empty">
              <Bot size={48} />
              <h2>¿En qué puedo ayudarte?</h2>
              <p className="muted">
                Interfaz tipo ChatGPT / Grok. Sin catálogo de proveedores en el cliente.
              </p>
              <div className="gpt-suggestions">
                {[
                  'Resume qué hace Agents Morf',
                  'Ayúdame a redactar un mensaje de ventas',
                  'Explícame cómo integrar la API de chat',
                ].map(s => (
                  <button type="button" key={s} className="secondary compact" onClick={() => setInput(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {history.map((m, i) => (
            <div key={i} className={`gpt-row ${m.role}`}>
              <div className={`gpt-bubble ${m.role}`}>
                <b>{m.role === 'user' ? 'Tú' : 'Asistente'}</b>
                <p>{m.content}</p>
              </div>
            </div>
          ))}
          {send.isPending && (
            <div className="gpt-row assistant">
              <div className="gpt-bubble assistant">
                <b>Asistente</b>
                <p className="muted">Pensando…</p>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {send.error && (
          <div className="error gpt-error">
            {send.error instanceof Error ? send.error.message : String(send.error)}
          </div>
        )}

        <form
          className="gpt-composer"
          onSubmit={e => {
            e.preventDefault()
            if (input.trim() && !send.isPending) send.mutate()
          }}
        >
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Escribe un mensaje…"
            rows={1}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (input.trim() && !send.isPending) send.mutate()
              }
            }}
          />
          <button type="submit" className="primary compact" disabled={!input.trim() || send.isPending}>
            <Send size={16} />
          </button>
        </form>
        <div className="gpt-meta">
          <span>{meta.provider ? `vía ${meta.provider}` : 'modelo en backend'}</span>
          <span>{meta.model || selectedAgent?.model || 'auto'}</span>
          {meta.latency != null && <span>{meta.latency} ms</span>}
          {conversationId && (
            <button type="button" className="ghost" onClick={newChat}>
              <Trash2 size={12} /> limpiar vista
            </button>
          )}
        </div>
      </section>
    </div>
  )
}
