import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  CheckCircle2,
  Copy,
  Download,
  Play,
  RefreshCw,
  TerminalSquare,
  Trash2,
  XCircle,
} from 'lucide-react'
import { Agent, ApiKey, ChatResponse, ToolCall, api } from './api'

type TerminalMessage = {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_calls?: ToolCall[]
  meta?: Record<string, unknown>
}

type ToolResultPayload = {
  conversation_id: string
  agent_id?: string
  tool_call_id: string
  tool_name?: string
  status: 'success' | 'failed' | 'rejected' | 'timeout'
  result: Record<string, unknown>
  error?: string
  idempotency_key?: string
}

function copyText(text: string) {
  void navigator.clipboard.writeText(text)
}

export function TerminalPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const { data: keys = [] } = useQuery({ queryKey: ['api-keys'], queryFn: () => api<ApiKey[]>('/api-keys') })
  const [agentId, setAgentId] = useState('')
  const [apiKeyPreview, setApiKeyPreview] = useState('')
  const [endUserId, setEndUserId] = useState('terminal-user')
  const [externalConversationId, setExternalConversationId] = useState('')
  const [mode, setMode] = useState<'automatic' | 'manual'>('automatic')
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<TerminalMessage[]>([])
  const [conversationId, setConversationId] = useState<string>()
  const [pendingTools, setPendingTools] = useState<ToolCall[]>([])
  const [simResult, setSimResult] = useState('{\n  "ok": true\n}')
  const [selectedTool, setSelectedTool] = useState<ToolCall | null>(null)
  const [lastRequest, setLastRequest] = useState<Record<string, unknown> | null>(null)
  const [lastResponse, setLastResponse] = useState<Record<string, unknown> | null>(null)
  const [meta, setMeta] = useState<Record<string, unknown>>({})
  const [logs, setLogs] = useState<string[]>([])
  const [error, setError] = useState('')

  const selectedAgent = useMemo(
    () => agents.find(a => a.id === agentId) || agents[0],
    [agents, agentId],
  )
  const activeAgentId = agentId || selectedAgent?.id || ''

  function pushLog(line: string) {
    setLogs(prev => [`${new Date().toISOString()}  ${line}`, ...prev].slice(0, 80))
  }

  const send = useMutation({
    mutationFn: async () => {
      setError('')
      if (!activeAgentId) {
        throw new Error('Selecciona un agente a la izquierda antes de enviar.')
      }
      const userText = input.trim()
      if (!userText) throw new Error('Escribe un mensaje.')
      const messages = [
        ...history
          .filter(m => m.role === 'user' || m.role === 'assistant')
          .map(m => ({ role: m.role, content: m.content })),
        { role: 'user' as const, content: userText },
      ]
      const body = {
        agent_id: activeAgentId || undefined,
        conversation_id: conversationId,
        end_user_id: endUserId || undefined,
        external_conversation_id: externalConversationId || undefined,
        messages,
        stream: false,
        remember: true,
        runtime: 'studio',
      }
      setLastRequest(body)
      pushLog(`POST /chat/completions agent=${selectedAgent?.slug || activeAgentId}`)
      // Abort after 90s so the UI never stays on "Enviando…" forever
      const controller = new AbortController()
      const timer = window.setTimeout(() => controller.abort(), 90_000)
      try {
        return await api<ChatResponse>('/chat/completions', {
          method: 'POST',
          body: JSON.stringify(body),
          signal: controller.signal,
        })
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          throw new Error('Timeout 90s: la API no respondió. Revisa backend/Groq e intenta de nuevo.')
        }
        throw err
      } finally {
        window.clearTimeout(timer)
      }
    },
    onSuccess: result => {
      const answer = result.choices[0]?.message
      const tools = answer?.tool_calls || []
      const content =
        answer?.content?.trim() ||
        (tools.length
          ? `Acciones: ${tools.map(t => `${t.name} (${t.status || 'ok'})`).join(', ')}`
          : '(sin texto del modelo)')
      setHistory(current => [
        ...current,
        { role: 'user', content: input },
        {
          role: 'assistant',
          content,
          tool_calls: tools,
        },
      ])
      setPendingTools(tools)
      if (tools[0]) setSelectedTool(tools[0])
      setConversationId(result.conversation_id)
      setInput('')
      setLastResponse(result as unknown as Record<string, unknown>)
      setMeta({
        provider: result.provider,
        model: result.model,
        memory_hits: result.memory_hits,
        knowledge_hits: result.knowledge_hits,
        latency_ms: result.latency_ms,
        request_id: result.request_id,
        tokens: result.usage,
        finish_reason: result.choices[0]?.finish_reason,
        tool_rounds: tools.length,
      })
      pushLog(
        `OK finish=${result.choices[0]?.finish_reason} tools=${tools.map(t => t.name).join(',') || '-'} provider=${result.provider} ${result.latency_ms ?? ''}ms`,
      )
    },
    onError: (err: Error) => {
      const msg = err.message || 'Error al enviar'
      setError(msg)
      pushLog(`ERROR ${msg}`)
      // still show the user message so the thread is not empty
      setHistory(current => [
        ...current,
        { role: 'user', content: input },
        { role: 'assistant', content: `⚠️ Error: ${msg}` },
      ])
      setInput('')
    },
  })

  const submitToolResult = useMutation({
    mutationFn: async (payload: ToolResultPayload) => {
      setLastRequest(payload)
      pushLog(`POST /tool-results call=${payload.tool_call_id} status=${payload.status}`)
      return api<Record<string, unknown>>('/tool-results', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    onSuccess: (result, vars) => {
      setHistory(current => [
        ...current,
        {
          role: 'tool',
          content: JSON.stringify({ tool_call_id: vars.tool_call_id, status: vars.status, result: vars.result }),
        },
        {
          role: 'assistant',
          content: String(result.content || (Array.isArray(result.tool_calls) ? `[more tool_calls]` : '')),
          tool_calls: (result.tool_calls as ToolCall[]) || [],
        },
      ])
      const more = (result.tool_calls as ToolCall[]) || []
      setPendingTools(more)
      if (more[0]) setSelectedTool(more[0])
      else setSelectedTool(null)
      setLastResponse(result)
      setMeta(prev => ({
        ...prev,
        provider: result.provider,
        model: result.model,
        memory_hits: result.memory_hits,
        knowledge_hits: result.knowledge_hits,
        finish_reason: result.finish_reason,
        tool_execution_id: result.tool_execution_id,
      }))
      pushLog(`tool continuation finish=${String(result.finish_reason)}`)
    },
    onError: (err: Error) => {
      setError(err.message)
      pushLog(`TOOL RESULT ERROR ${err.message}`)
    },
  })

  function simulateTool(status: ToolResultPayload['status'] = 'success') {
    if (!selectedTool || !conversationId) {
      setError('Selecciona un tool_call pendiente y una conversación activa')
      return
    }
    let parsed: Record<string, unknown> = {}
    try {
      parsed = JSON.parse(simResult || '{}') as Record<string, unknown>
    } catch {
      setError('El JSON del simulador no es válido')
      return
    }
    submitToolResult.mutate({
      conversation_id: conversationId,
      agent_id: activeAgentId || undefined,
      tool_call_id: selectedTool.id,
      tool_name: selectedTool.name,
      status,
      result: parsed,
      error: status === 'success' ? '' : 'Simulated failure',
      idempotency_key: `term-${selectedTool.id}-${Date.now()}`,
    })
  }

  async function downloadManifest() {
    if (!activeAgentId) return
    const manifest = await api<Record<string, unknown>>(`/agents/${activeAgentId}/integration-manifest`)
    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `integration-manifest-${selectedAgent?.slug || activeAgentId}.json`
    a.click()
    URL.revokeObjectURL(url)
    pushLog('Downloaded integration manifest')
  }

  function downloadTranscript() {
    const blob = new Blob([JSON.stringify({ conversation_id: conversationId, history, meta }, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `terminal-transcript-${conversationId || 'new'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const curlExample = useMemo(() => {
    const base = window.location.origin
    return `curl -X POST ${base}/api/v1/chat/completions \\
  -H "Authorization: Bearer am_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"agent":"${selectedAgent?.slug || 'agent-slug'}","messages":[{"role":"user","content":"Hola"}]}'`
  }, [selectedAgent])

  const pythonExample = useMemo(() => {
    const base = window.location.origin
    return `import requests
r = requests.post(
  "${base}/api/v1/chat/completions",
  headers={"Authorization": "Bearer am_YOUR_KEY"},
  json={"agent": "${selectedAgent?.slug || 'agent-slug'}", "messages": [{"role": "user", "content": "Hola"}]},
)
print(r.json())`
  }, [selectedAgent])

  const jsExample = useMemo(() => {
    const base = window.location.origin
    return `await fetch("${base}/api/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer am_YOUR_KEY",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    agent: "${selectedAgent?.slug || 'agent-slug'}",
    messages: [{ role: "user", content: "Hola" }],
  }),
})`
  }, [selectedAgent])

  return (
    <section className="panel terminal-panel">
      <div className="panel-head">
        <div>
          <p className="eyebrow">SECURE PLAYGROUND</p>
          <h1>Agents Morf Terminal</h1>
          <p className="muted">
            Agente operativo real: workspace sandbox + <b>SSH remoto</b> + web. Ejemplo:
            <code> ssh root@86.48.20.221 Gaia1234</code> — entra, explora /www y resume.
            Solo tools de negocio del cliente son demo; SSH/workspace/web SÍ se ejecutan.
          </p>
        </div>
        <div className="row-actions">
          <button type="button" className="secondary compact" onClick={() => { setHistory([]); setConversationId(undefined); setPendingTools([]); setSelectedTool(null); pushLog('Conversation cleared') }}>
            <Trash2 size={14} /> Limpiar
          </button>
          <button type="button" className="secondary compact" onClick={downloadTranscript}><Download size={14} /> Transcript</button>
          <button type="button" className="secondary compact" onClick={() => void downloadManifest()}><Download size={14} /> Manifest</button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="terminal-grid">
        <aside className="terminal-side">
          <h3><TerminalSquare size={16} /> Contexto</h3>
          <label>Agente
            <select value={activeAgentId} onChange={e => setAgentId(e.target.value)}>
              <option value="">— seleccionar —</option>
              {agents.map(a => <option key={a.id} value={a.id}>{a.name} · v{a.current_version}</option>)}
            </select>
          </label>
          <label>Versión (lectura)
            <input readOnly value={selectedAgent ? `v${selectedAgent.current_version}.0.0` : '—'} />
          </label>
          <label>API key de prueba (solo prefijo)
            <select value={apiKeyPreview} onChange={e => setApiKeyPreview(e.target.value)}>
              <option value="">Sesión JWT actual</option>
              {keys.map(k => <option key={k.id} value={k.prefix}>{k.name} · {k.prefix}…</option>)}
            </select>
          </label>
          <label>Modo modelo
            <select value={mode} onChange={e => setMode(e.target.value as 'automatic' | 'manual')}>
              <option value="automatic">Automático (router)</option>
              <option value="manual">Manual / default org</option>
            </select>
          </label>
          <label>end_user_id
            <input value={endUserId} onChange={e => setEndUserId(e.target.value)} />
          </label>
          <label>external_conversation_id
            <input value={externalConversationId} onChange={e => setExternalConversationId(e.target.value)} placeholder="opcional" />
          </label>
          <div className="chips">
            <span>runtime=studio</span>
            <span>SSH real</span>
            <span>workspace real</span>
            <span>negocio=demo</span>
          </div>
          <p className="muted small">
            Org: {localStorage.getItem('organization_id')?.slice(0, 8) || '—'}…
          </p>
        </aside>

        <div className="terminal-center">
          <div className="terminal-messages">
            {history.length === 0 && (
              <div className="empty">
                <TerminalSquare size={36} />
                <p>
                  <b>Usa solo este panel en agent.codemorf.tech</b> (no abras el HTML de Downloads — es un mockup sin API).
                </p>
                <p className="muted">
                  Ejemplo SSH: <code>ssh root@86.48.20.221 Gaia1234</code>
                  <br />
                  Ejemplo workspace: <code>lista el workspace y lee README.md</code>
                </p>
              </div>
            )}
            {history.map((m, i) => (
              <article key={i} className={`term-msg role-${m.role}`}>
                <header>{m.role}</header>
                <pre>{m.content}</pre>
                {m.tool_calls && m.tool_calls.length > 0 && (
                  <div className="tool-call-list">
                    {m.tool_calls.map(t => (
                      <button
                        type="button"
                        key={t.id}
                        className={selectedTool?.id === t.id ? 'tool-pill active' : 'tool-pill'}
                        onClick={() => setSelectedTool(t)}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
          <form
            className="terminal-compose"
            onSubmit={e => {
              e.preventDefault()
              if (!input.trim()) return
              send.mutate()
            }}
          >
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Mensaje al agente…"
              rows={3}
            />
            <button className="primary" type="submit" disabled={send.isPending || !activeAgentId}>
              <Play size={16} /> {send.isPending ? 'Enviando…' : 'Enviar'}
            </button>
          </form>
        </div>

        <aside className="terminal-side terminal-inspector">
          <h3>Inspector</h3>
          <div className="meta-grid">
            {Object.entries(meta).map(([k, v]) => (
              <div key={k}><span>{k}</span><strong>{typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}</strong></div>
            ))}
          </div>

          <h4>Client Tool Simulator</h4>
          <p className="muted small">
            Solo para tools de <b>negocio del cliente</b> (sales.*, restaurant.*). 
            SSH, workspace y web ya se ejecutan en el servidor — no hace falta simularlos.
          </p>
          {pendingTools.length === 0 && <p className="muted">Sin tool_calls pendientes.</p>}
          {pendingTools.length > 0 && (
            <label>Tool call
              <select
                value={selectedTool?.id || ''}
                onChange={e => setSelectedTool(pendingTools.find(t => t.id === e.target.value) || null)}
              >
                {pendingTools.map(t => <option key={t.id} value={t.id}>{t.name} · {t.id}</option>)}
              </select>
            </label>
          )}
          {selectedTool && (
            <pre className="code-block">{JSON.stringify({ id: selectedTool.id, name: selectedTool.name, arguments: selectedTool.arguments, execution_mode: selectedTool.execution_mode }, null, 2)}</pre>
          )}
          <label>Resultado simulado (JSON)
            <textarea value={simResult} onChange={e => setSimResult(e.target.value)} rows={6} />
          </label>
          <div className="row-actions">
            <button type="button" className="primary compact" onClick={() => simulateTool('success')} disabled={!selectedTool || submitToolResult.isPending}>
              <CheckCircle2 size={14} /> success
            </button>
            <button type="button" className="secondary compact" onClick={() => simulateTool('failed')} disabled={!selectedTool}>
              <XCircle size={14} /> failed
            </button>
            <button type="button" className="secondary compact" onClick={() => simulateTool('rejected')} disabled={!selectedTool}>
              reject
            </button>
          </div>

          <h4>Request JSON</h4>
          <pre className="code-block">{JSON.stringify(lastRequest, null, 2)}</pre>
          <h4>Response JSON</h4>
          <pre className="code-block">{JSON.stringify(lastResponse, null, 2)}</pre>

          <h4>Copiar ejemplos</h4>
          <div className="row-actions">
            <button type="button" className="secondary compact" onClick={() => copyText(curlExample)}><Copy size={14} /> curl</button>
            <button type="button" className="secondary compact" onClick={() => copyText(pythonExample)}><Copy size={14} /> Python</button>
            <button type="button" className="secondary compact" onClick={() => copyText(jsExample)}><Copy size={14} /> JS</button>
          </div>

          <h4>Logs</h4>
          <div className="term-logs">
            {logs.map((l, i) => <div key={i}>{l}</div>)}
            {logs.length === 0 && <span className="muted">Sin eventos</span>}
          </div>
          <button type="button" className="secondary compact" onClick={() => setLogs([])}><RefreshCw size={14} /> Limpiar logs</button>
        </aside>
      </div>
    </section>
  )
}
