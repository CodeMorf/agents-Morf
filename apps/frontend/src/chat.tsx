/** Modern client chat — memory & training applied in backend; UI shows what matters. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Bot,
  Brain,
  BookOpen,
  GraduationCap,
  HardDrive,
  MessageSquarePlus,
  Moon,
  Send,
  Sparkles,
  Sun,
  Trash2,
} from 'lucide-react'
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
  memory_hits?: number
  knowledge_hits?: number
  trained?: boolean
  tool_calls?: Array<{ id?: string; name: string; status?: string; simulated?: boolean; arguments?: Record<string, unknown> }>
}

type Theme = 'dark' | 'light'

type MemoryHighlight = {
  id: string
  kind: string
  scope: string
  content: string
  importance: number
  source: string
}

type MemoryBank = {
  total_items: number
  total_bytes: number
  total_kb: number
  total_mb: number
  items: MemoryHighlight[]
}

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
  const [meta, setMeta] = useState<{
    provider?: string
    model?: string
    latency?: number
    memory?: number
    knowledge?: number
  }>({})
  const bottomRef = useRef<HTMLDivElement>(null)
  const selectedAgent = useMemo(
    () => agents.find(a => a.id === agentId) || agents[0],
    [agents, agentId],
  )

  const { data: memoryBank } = useQuery({
    queryKey: ['memory-highlights', selectedAgent?.id],
    queryFn: () =>
      api<MemoryBank>(
        `/memory/highlights?limit=10${selectedAgent?.id ? `&agent_id=${selectedAgent.id}` : ''}`,
      ),
    enabled: Boolean(selectedAgent?.id || agents.length >= 0),
  })

  useEffect(() => {
    if (!agentId && agents[0]) setAgentId(agents[0].id)
  }, [agents, agentId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, meta])

  const loadMessages = useMutation({
    mutationFn: (id: string) => api<ChatMessage[]>(`/conversations/${id}/messages`),
    onSuccess: (rows, id) => {
      setConversationId(id)
      setHistory(
        rows
          .filter(r => r.role === 'user' || r.role === 'assistant')
          .map(r => ({ role: r.role, content: r.content || '', id: r.id, model: r.model })),
      )
    },
  })

  const [sendError, setSendError] = useState('')
  const send = useMutation({
    mutationFn: async () => {
      setSendError('')
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
          // Studio: platform tools run for real; client business tools get demo results so the agent finishes.
          runtime: 'studio',
        }),
      })
    },
    onError: (err: Error) => {
      setSendError(err.message || 'Error al chatear')
    },
    onSuccess: result => {
      const answer = result.choices[0]?.message
      const mem = result.memory_hits ?? 0
      const know = result.knowledge_hits ?? 0
      const tools = answer?.tool_calls || []
      const body =
        answer?.content?.trim() ||
        (tools.length
          ? `He ejecutado ${tools.length} acción(es): ${tools.map(t => t.name).join(', ')}. ${
              tools.some(t => (t as { status?: string }).status === 'simulated' || (t as { simulated?: boolean }).simulated)
                ? '(incluye resultados DEMO de Studio — en producción tu backend ejecuta las tools de negocio)'
                : ''
            }`
          : 'Sin respuesta del modelo. Revisa proveedores (Groq) o el agente seleccionado.')
      setHistory(h => [
        ...h,
        { role: 'user', content: input },
        {
          role: 'assistant',
          content: body,
          tool_calls: tools.map(t => ({
            id: t.id,
            name: t.name,
            status: t.status,
            simulated: Boolean((t as { simulated?: boolean }).simulated) || t.status === 'simulated',
            arguments: t.arguments,
          })),
          memory_hits: mem,
          knowledge_hits: know,
          trained: Boolean(selectedAgent?.memory_enabled || selectedAgent?.knowledge_enabled),
          provider: result.provider,
          model: result.model,
        },
      ])
      setConversationId(result.conversation_id)
      setMeta({
        provider: result.provider,
        model: result.model,
        latency: result.latency_ms,
        memory: mem,
        knowledge: know,
      })
      setInput('')
      refetchConvos()
      queryClient.invalidateQueries({ queryKey: ['usage'] })
      queryClient.invalidateQueries({ queryKey: ['memory-highlights'] })
    },
  })

  function newChat() {
    setConversationId(undefined)
    setHistory([])
    setMeta({})
    setInput('')
  }

  const bankMb = memoryBank?.total_mb ?? 0
  const bankKb = memoryBank?.total_kb ?? 0
  const bankLabel =
    bankMb >= 0.01 ? `${bankMb.toFixed(3)} MB` : `${bankKb.toFixed(1)} KB`

  return (
    <div className="gpt-shell gpt-shell-3">
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
            <p className="eyebrow">CHAT INTELIGENTE</p>
            <h1>{selectedAgent?.name || 'Agents Morf'}</h1>
            <p className="muted">
              Conversa con el agente. Si necesita ejecutar algo, devuelve tool calls (cliente o demo Studio). Router dinámico · sin shell VPS.
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
              {agents.length === 0 && <option value="">Sin agentes — instala una plantilla en /agents</option>}
              {agents.map(a => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </header>

        {agents.length === 0 && (
          <div className="warning-banner" style={{ margin: '0 18px 8px' }}>
            No tienes agentes instalados. Ve a <a href="/agents"><b>Agentes → Catálogo</b></a> y pulsa
            <b> Usar plantilla</b> (p. ej. Venta AI o Chatbot de soporte). Sin agente, el chat no puede actuar con tools.
          </div>
        )}

        <div className="gpt-context-bar">
          <span className="gpt-chip">
            <HardDrive size={14} /> Banco memoria: <b>{bankLabel}</b>
          </span>
          <span className="gpt-chip">
            <Brain size={14} /> {memoryBank?.total_items ?? 0} recuerdos
          </span>
          <span className="gpt-chip">
            <GraduationCap size={14} /> Entrenamiento:{' '}
            {selectedAgent?.memory_enabled || selectedAgent?.knowledge_enabled ? 'activo' : 'básico'}
          </span>
          <span className="gpt-chip">
            <Sparkles size={14} /> Studio · tools activos
          </span>
        </div>

        {sendError && <div className="error" style={{ margin: '0 18px 8px' }}>{sendError}</div>}
        <div className="gpt-messages">
          {history.length === 0 && (
            <div className="gpt-hero-empty">
              <Bot size={48} />
              <h2>¿En qué puedo ayudarte?</h2>
              <p className="muted">
                Este agente puede actuar: memoria, knowledge, fecha/cálculos y tools de plantilla (demo en Studio).
              </p>
              <div className="gpt-suggestions">
                {[
                  '¿Qué puedes hacer ahora? (como Grok Build)',
                  'Lista el workspace y lee README.md',
                  'Lee src/hello.py, mejóralo y ejecuta python src/hello.py',
                  'Busca en internet: noticias de IA esta semana',
                  'Calcula 15% de comisión sobre 2400',
                  'Simula una cotización de venta del plan Pro',
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
                <b>{m.role === 'user' ? 'Tú' : 'Agente'}</b>
                <p>{m.content}</p>
                {m.role === 'assistant' && m.tool_calls && m.tool_calls.length > 0 && (
                  <div className="tool-call-list" style={{ marginTop: 10 }}>
                    {m.tool_calls.map((t, ti) => (
                      <span key={t.id || ti} className="tool-pill active" title={JSON.stringify(t.arguments || {})}>
                        ⚡ {t.name}
                        {t.simulated || t.status === 'simulated' ? ' · demo' : t.status ? ` · ${t.status}` : ''}
                      </span>
                    ))}
                  </div>
                )}
                {m.role === 'assistant' && (m.memory_hits != null || m.knowledge_hits != null) && (
                  <div className="gpt-msg-tags">
                    {(m.memory_hits ?? 0) > 0 && (
                      <span>
                        <Brain size={12} /> Memoria ×{m.memory_hits}
                      </span>
                    )}
                    {(m.knowledge_hits ?? 0) > 0 && (
                      <span>
                        <BookOpen size={12} /> Conocimiento ×{m.knowledge_hits}
                      </span>
                    )}
                    {m.trained && (
                      <span>
                        <GraduationCap size={12} /> Entrenado
                      </span>
                    )}
                    {m.provider && (
                      <span>
                        <Sparkles size={12} /> {m.provider}/{m.model}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {send.isPending && (
            <div className="gpt-row assistant">
              <div className="gpt-bubble assistant">
                <b>Asistente</b>
                <p className="muted">Pensando con memoria y entrenamiento…</p>
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
          {(meta.memory ?? 0) > 0 && <span>Memoria usada: {meta.memory}</span>}
          {(meta.knowledge ?? 0) > 0 && <span>RAG: {meta.knowledge}</span>}
          {meta.latency != null && <span>{meta.latency} ms</span>}
          {conversationId && (
            <button type="button" className="ghost" onClick={newChat}>
              <Trash2 size={12} /> limpiar vista
            </button>
          )}
        </div>
      </section>

      {/* Memory bank — important facts only (read-only for client) */}
      <aside className="gpt-memory-panel">
        <div className="gpt-mb-head">
          <HardDrive size={18} />
          <div>
            <strong>Memoria del agente</strong>
            <small>Solo lectura · administrada en backend</small>
          </div>
        </div>
        <div className="gpt-mb-size">
          <b>{bankLabel}</b>
          <span>{memoryBank?.total_items ?? 0} ítems activos</span>
        </div>
        <p className="gpt-mb-label">Cosas importantes</p>
        <div className="gpt-mb-list">
          {(memoryBank?.items || []).map(item => (
            <article key={item.id} className="gpt-mb-card">
              <div className="gpt-mb-card-top">
                <span className="gpt-chip tiny">{item.kind}</span>
                <span className="muted tiny">{Math.round(item.importance * 100)}%</span>
              </div>
              <p>{item.content}</p>
            </article>
          ))}
          {(!memoryBank?.items || memoryBank.items.length === 0) && (
            <p className="muted gpt-empty-side">
              Aún no hay recuerdos importantes. El chat irá memorizando hechos útiles
              automáticamente (backend).
            </p>
          )}
        </div>
        <div className="gpt-mb-foot muted">
          <Brain size={14} /> No editas memoria aquí — el sistema la usa al responder.
        </div>
      </aside>
    </div>
  )
}
