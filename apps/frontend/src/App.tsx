import { useMemo, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  BookOpen,
  Bot,
  BrainCircuit,
  Braces,
  Database,
  Gauge,
  KeyRound,
  LogOut,
  MessagesSquare,
  Network,
  Plus,
  Save,
  Settings,
  Sparkles,
  TestTube2,
  ThumbsDown,
  ThumbsUp,
  MessageCircleWarning,
  Wrench,
} from 'lucide-react'
import {
  Agent,
  ApiKey,
  ApiKeyCreated,
  ChatResponse,
  Dashboard,
  Document,
  Feedback,
  KnowledgeBase,
  MemoryItem,
  Organization,
  Provider,
  Tool,
  TrainingDataset,
  TrainingExample,
  api,
} from './api'

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & { label: string }
function Field({ label, ...props }: FieldProps) {
  return <label>{label}<input {...props} /></label>
}

function Textarea({ label, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return <label>{label}<textarea {...props} /></label>
}

function Select({ label, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return <label>{label}<select {...props}>{children}</select></label>
}

function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const tokens = await api<{ access_token: string }>('/auth/login', {
        method: 'POST', body: JSON.stringify({ email, password }),
      })
      localStorage.setItem('access_token', tokens.access_token)
      const organizations = await api<Organization[]>('/organizations')
      if (organizations[0]) localStorage.setItem('organization_id', organizations[0].id)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    }
  }
  return <main className="login-shell">
    <section className="login-card">
      <img src="/agents-morf-logo.png" className="login-logo" alt="Agents Morf" />
      <p className="eyebrow">AUTONOMOUS AI AGENT OPERATING SYSTEM</p>
      <h1>Agent control plane</h1>
      <p className="muted">Build, train, test and expose autonomous agents through one secure API.</p>
      <form onSubmit={submit} className="stack">
        <Field label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
        <Field label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <div className="error">{error}</div>}
        <button className="primary">Sign in</button>
      </form>
    </section>
  </main>
}

const nav = [
  ['/', 'Overview', Gauge],
  ['/agents', 'Agents', Bot],
  ['/studio', 'Studio', MessagesSquare],
  ['/memory', 'Memory', BrainCircuit],
  ['/knowledge', 'Knowledge', BookOpen],
  ['/training', 'Training', TestTube2],
  ['/feedback', 'Feedback', MessageCircleWarning],
  ['/tools', 'Tools', Wrench],
  ['/providers', 'Providers', Sparkles],
  ['/api-keys', 'API keys', KeyRound],
  ['/docs', 'API docs', Braces],
  ['/settings', 'Settings', Settings],
] as const

function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  return <div className="app-shell">
    <aside>
      <div className="brand">
        <img src="/agents-morf-logo.png" alt="Agents Morf" />
        <div><strong>Agents Morf</strong><small>CodeMorf AI Platform</small></div>
      </div>
      <nav>{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === '/'}><Icon size={18} />{label}</NavLink>)}</nav>
      <button className="logout" onClick={() => { localStorage.clear(); navigate('/login') }}><LogOut size={18} /> Sign out</button>
    </aside>
    <section className="workspace">
      <header>
        <div><p className="eyebrow">AGENT.CODEMORF.TECH</p><h2>Autonomous agent infrastructure</h2></div>
        <span className="status"><i /> API online</span>
      </header>
      {children}
    </section>
  </div>
}

function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow: string; title: string; subtitle?: string; action?: React.ReactNode }) {
  return <div className="panel-head"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>{action}</div>
}

function ErrorBox({ error }: { error: unknown }) {
  return error ? <div className="error">{error instanceof Error ? error.message : String(error)}</div> : null
}

function Overview() {
  const { data, error } = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') })
  const cards = data ? Object.entries(data) : []
  return <div>
    <div className="hero">
      <div><p className="eyebrow">AI ORCHESTRATION LAYER</p><h1>One agent API. Every product.</h1><p>Train agents once, then consume them from ALLSENDER, EcoMarket, restaurants, calendars and future applications.</p></div>
      <Network size={76} />
    </div>
    <ErrorBox error={error} />
    <div className="metric-grid">{cards.map(([key, value]) => <article className="metric" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value}</strong></article>)}</div>
    <section className="panel">
      <h3>Separation of responsibilities</h3>
      <div className="three">
        <div><b>Agents Morf reasons</b><p>Conversation, memory, knowledge, model routing, tools and guardrails.</p></div>
        <div><b>Product backends execute</b><p>Email, WhatsApp, payments, reservations, orders and domain data stay in each platform.</p></div>
        <div><b>APIs connect everything</b><p>OpenAI-compatible chat, API keys and documented HTTP tools.</p></div>
      </div>
    </section>
  </div>
}

function AgentsPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '', description: '', system_prompt: '', instructions: '' })
  const create = useMutation({
    mutationFn: () => api<Agent>('/agents', {
      method: 'POST', body: JSON.stringify({ ...form, memory_enabled: true, knowledge_enabled: true }),
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['agents'] }); setOpen(false); setForm({ name: '', slug: '', description: '', system_prompt: '', instructions: '' }) },
  })
  return <section className="panel">
    <PageHeader eyebrow="AGENT BUILDER" title="Agents" subtitle="Create versioned agents with independent prompts, models, memory and tools." action={<button className="primary compact" onClick={() => setOpen(!open)}><Plus size={16} /> New agent</button>} />
    <ErrorBox error={error || create.error} />
    {open && <form className="form-grid create-box" onSubmit={e => { e.preventDefault(); create.mutate() }}>
      <Field label="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value, slug: form.slug || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') })} required />
      <Field label="Slug" value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value })} required />
      <Field label="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
      <Textarea label="System prompt" value={form.system_prompt} onChange={e => setForm({ ...form, system_prompt: e.target.value })} required />
      <Textarea label="Operational instructions" value={form.instructions} onChange={e => setForm({ ...form, instructions: e.target.value })} />
      <button className="primary"><Save size={16} /> Create agent</button>
    </form>}
    <div className="card-grid">{data.map(agent => <article className="entity-card" key={agent.id}>
      <div className="entity-title"><Bot size={24} /><div><h3>{agent.name}</h3><small>{agent.slug} · v{agent.current_version}</small></div></div>
      <p>{agent.description || 'No description'}</p>
      <div className="chips"><span>{agent.memory_enabled ? 'Memory on' : 'Memory off'}</span><span>{agent.knowledge_enabled ? 'RAG on' : 'RAG off'}</span><span>{agent.model || 'Provider model'}</span></div>
    </article>)}</div>
  </section>
}

function StudioPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const [agentId, setAgentId] = useState('')
  const [endUserId, setEndUserId] = useState('demo-user')
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<Array<{ role: string; content: string }>>([])
  const [conversationId, setConversationId] = useState<string>()
  const [meta, setMeta] = useState<{ provider?: string; model?: string; memory?: number; knowledge?: number }>({})
  const [feedbackTarget, setFeedbackTarget] = useState<{ conversationId: string; messageId: string }>()
  const feedback = useMutation({
    mutationFn: (rating: number) => api<Feedback>('/feedback', {
      method: 'POST',
      body: JSON.stringify({ agent_id: agentId || undefined, conversation_id: feedbackTarget?.conversationId, message_id: feedbackTarget?.messageId, end_user_id: endUserId || undefined, rating, source: 'studio' }),
    }),
  })
  const send = useMutation({
    mutationFn: async () => {
      const messages = [...history, { role: 'user', content: input }]
      return api<ChatResponse>('/chat/completions', {
        method: 'POST',
        body: JSON.stringify({ agent_id: agentId || undefined, conversation_id: conversationId, end_user_id: endUserId || undefined, messages, stream: false, remember: true }),
      })
    },
    onSuccess: result => {
      const answer = result.choices[0].message
      setHistory(current => [...current, { role: 'user', content: input }, { role: 'assistant', content: answer.content || `[Tool call: ${answer.tool_calls.map(tool => tool.name).join(', ')}]` }])
      setConversationId(result.conversation_id)
      setFeedbackTarget({ conversationId: result.conversation_id, messageId: result.assistant_message_id })
      feedback.reset()
      setMeta({ provider: result.provider, model: result.model, memory: result.memory_hits, knowledge: result.knowledge_hits })
      setInput('')
    },
  })
  return <section className="panel studio">
    <PageHeader eyebrow="PLAYGROUND" title="Agent Studio" subtitle="Test the same API your other products will consume." />
    <div className="studio-toolbar">
      <Select label="Agent" value={agentId} onChange={e => setAgentId(e.target.value)}><option value="">Default active agent</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</Select>
      <Field label="External end-user ID" value={endUserId} onChange={e => setEndUserId(e.target.value)} />
      <button className="secondary" onClick={() => { setHistory([]); setConversationId(undefined); setFeedbackTarget(undefined); setMeta({}) }}>New conversation</button>
    </div>
    <div className="chat-log">{history.length === 0 && <div className="empty"><MessagesSquare size={40} /><p>Start a conversation. Memory and knowledge hits will appear below.</p></div>}{history.map((item, index) => <div key={index} className={`bubble ${item.role}`}><b>{item.role}</b><p>{item.content}</p></div>)}</div>
    <ErrorBox error={send.error} />
    <form className="composer" onSubmit={e => { e.preventDefault(); if (input.trim()) send.mutate() }}><textarea value={input} onChange={e => setInput(e.target.value)} placeholder="Ask the agent..." /><button className="primary" disabled={send.isPending}>{send.isPending ? 'Thinking…' : 'Send'}</button></form>
    <div className="run-meta"><span>Provider: {meta.provider || '—'}</span><span>Model: {meta.model || '—'}</span><span>Memory hits: {meta.memory ?? 0}</span><span>Knowledge hits: {meta.knowledge ?? 0}</span></div>
    {feedbackTarget && <div className="feedback-actions"><span>Was this response useful?</span><button className="secondary compact" onClick={() => feedback.mutate(1)} disabled={feedback.isPending}><ThumbsUp size={15} /> Yes</button><button className="secondary compact" onClick={() => feedback.mutate(-1)} disabled={feedback.isPending}><ThumbsDown size={15} /> No</button>{feedback.isSuccess && <small>Feedback saved for review.</small>}</div>}
  </section>
}

function MemoryPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['memory'], queryFn: () => api<MemoryItem[]>('/memory') })
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const [form, setForm] = useState({ agent_id: '', end_user_id: '', scope: 'agent', kind: 'fact', content: '', importance: 0.7 })
  const create = useMutation({
    mutationFn: () => api<MemoryItem>('/memory', { method: 'POST', body: JSON.stringify({ ...form, agent_id: form.agent_id || undefined, end_user_id: form.end_user_id || undefined }) }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['memory'] }); setForm({ ...form, content: '' }) },
  })
  return <section className="panel">
    <PageHeader eyebrow="LONG-TERM CONTEXT" title="Memory" subtitle="Durable facts and preferences scoped to organizations, agents, users or conversations." />
    <form className="form-grid create-box" onSubmit={e => { e.preventDefault(); create.mutate() }}>
      <Select label="Agent" value={form.agent_id} onChange={e => setForm({ ...form, agent_id: e.target.value })}><option value="">All/default</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</Select>
      <Select label="Scope" value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })}><option>organization</option><option>agent</option><option>end_user</option><option>conversation</option></Select>
      <Select label="Kind" value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}><option>fact</option><option>preference</option><option>instruction</option><option>summary</option><option>outcome</option></Select>
      <Field label="End-user ID" value={form.end_user_id} onChange={e => setForm({ ...form, end_user_id: e.target.value })} />
      <Textarea label="Memory content" value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} required />
      <button className="primary"><Plus size={16} /> Add memory</button>
    </form>
    <ErrorBox error={error || create.error} />
    <div className="table-wrap"><table><thead><tr><th>Content</th><th>Scope</th><th>Kind</th><th>User</th><th>Source</th></tr></thead><tbody>{data.map(item => <tr key={item.id}><td><b>{item.content}</b></td><td>{item.scope}</td><td>{item.kind}</td><td>{item.end_user_id || '—'}</td><td>{item.source}</td></tr>)}</tbody></table></div>
  </section>
}

function KnowledgePage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['knowledge'], queryFn: () => api<KnowledgeBase[]>('/knowledge-bases') })
  const [selected, setSelected] = useState('')
  const [name, setName] = useState('')
  const [doc, setDoc] = useState({ title: '', content: '' })
  const [uploadFile, setUploadFile] = useState<File>()
  const documents = useQuery({ queryKey: ['documents', selected], queryFn: () => api<Document[]>(`/knowledge-bases/${selected}/documents`), enabled: Boolean(selected) })
  const createKb = useMutation({ mutationFn: () => api<KnowledgeBase>('/knowledge-bases', { method: 'POST', body: JSON.stringify({ name }) }), onSuccess: result => { setSelected(result.id); setName(''); queryClient.invalidateQueries({ queryKey: ['knowledge'] }) } })
  const addDoc = useMutation({ mutationFn: () => api<Document>(`/knowledge-bases/${selected}/documents/text`, { method: 'POST', body: JSON.stringify(doc) }), onSuccess: () => { setDoc({ title: '', content: '' }); queryClient.invalidateQueries({ queryKey: ['documents', selected] }) } })
  const uploadDoc = useMutation({ mutationFn: () => { const body = new FormData(); if (uploadFile) body.append('file', uploadFile); return api<Document>(`/knowledge-bases/${selected}/documents/upload`, { method: 'POST', body }) }, onSuccess: () => { setUploadFile(undefined); queryClient.invalidateQueries({ queryKey: ['documents', selected] }) } })
  return <section className="panel">
    <PageHeader eyebrow="RAG" title="Knowledge bases" subtitle="Upload approved business knowledge and link it to agents." />
    <div className="split">
      <div>
        <form className="inline-form" onSubmit={e => { e.preventDefault(); createKb.mutate() }}><input placeholder="New knowledge base" value={name} onChange={e => setName(e.target.value)} /><button className="primary compact"><Plus size={16} /> Create</button></form>
        <div className="selection-list">{data.map(kb => <button key={kb.id} className={selected === kb.id ? 'selected' : ''} onClick={() => setSelected(kb.id)}><Database size={18} /><span><b>{kb.name}</b><small>{kb.description || 'No description'}</small></span></button>)}</div>
      </div>
      <div>
        {selected ? <>
          <form className="stack create-box" onSubmit={e => { e.preventDefault(); addDoc.mutate() }}><Field label="Document title" value={doc.title} onChange={e => setDoc({ ...doc, title: e.target.value })} required /><Textarea label="Text or Markdown content" value={doc.content} onChange={e => setDoc({ ...doc, content: e.target.value })} required /><button className="primary">Index document</button></form>
          <form className="inline-form create-box" onSubmit={e => { e.preventDefault(); if (uploadFile) uploadDoc.mutate() }}><label className="file-input">Upload PDF, DOCX, TXT, Markdown, CSV or JSON<input type="file" accept=".pdf,.docx,.txt,.md,.csv,.json" onChange={e => setUploadFile(e.target.files?.[0])} /></label><button className="secondary compact" disabled={!uploadFile || uploadDoc.isPending}>{uploadDoc.isPending ? 'Indexing…' : 'Upload and index'}</button></form>
          <div className="document-list">{documents.data?.map(item => <div key={item.id}><BookOpen size={18} /><span><b>{item.title}</b><small>{item.status} · {item.chunk_count} chunks</small></span></div>)}</div>
        </> : <div className="empty"><BookOpen size={38} /><p>Select or create a knowledge base.</p></div>}
      </div>
    </div>
    <ErrorBox error={error || createKb.error || addDoc.error || uploadDoc.error || documents.error} />
  </section>
}

function TrainingPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['datasets'], queryFn: () => api<TrainingDataset[]>('/training/datasets') })
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const [selected, setSelected] = useState('')
  const [datasetName, setDatasetName] = useState('')
  const [example, setExample] = useState({ agent_id: '', input_text: '', expected_output: '', context: '' })
  const examples = useQuery({ queryKey: ['training-examples', selected], queryFn: () => api<TrainingExample[]>(`/training/datasets/${selected}/examples`), enabled: Boolean(selected) })
  const createDataset = useMutation({ mutationFn: () => api<TrainingDataset>('/training/datasets', { method: 'POST', body: JSON.stringify({ name: datasetName }) }), onSuccess: result => { setSelected(result.id); setDatasetName(''); queryClient.invalidateQueries({ queryKey: ['datasets'] }) } })
  const createExample = useMutation({ mutationFn: () => api<TrainingExample>(`/training/datasets/${selected}/examples`, { method: 'POST', body: JSON.stringify({ ...example, agent_id: example.agent_id || undefined }) }), onSuccess: () => { setExample({ ...example, input_text: '', expected_output: '', context: '' }); queryClient.invalidateQueries({ queryKey: ['training-examples', selected] }) } })
  return <section className="panel">
    <PageHeader eyebrow="BEHAVIORAL TRAINING" title="Training Studio" subtitle="Teach behavior with curated examples, prompts, knowledge and evaluations—without coupling to product databases." />
    <div className="split">
      <div>
        <form className="inline-form" onSubmit={e => { e.preventDefault(); createDataset.mutate() }}><input placeholder="Dataset name" value={datasetName} onChange={e => setDatasetName(e.target.value)} /><button className="primary compact"><Plus size={16} /> Create</button></form>
        <div className="selection-list">{data.map(item => <button key={item.id} className={selected === item.id ? 'selected' : ''} onClick={() => setSelected(item.id)}><TestTube2 size={18} /><span><b>{item.name}</b><small>{item.status}</small></span></button>)}</div>
      </div>
      <div>{selected ? <>
        <form className="stack create-box" onSubmit={e => { e.preventDefault(); createExample.mutate() }}>
          <Select label="Agent" value={example.agent_id} onChange={e => setExample({ ...example, agent_id: e.target.value })}><option value="">General example</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</Select>
          <Textarea label="User input" value={example.input_text} onChange={e => setExample({ ...example, input_text: e.target.value })} required />
          <Textarea label="Expected agent response" value={example.expected_output} onChange={e => setExample({ ...example, expected_output: e.target.value })} required />
          <Textarea label="Optional context" value={example.context} onChange={e => setExample({ ...example, context: e.target.value })} />
          <button className="primary">Add training example</button>
        </form>
        <div className="example-list">{examples.data?.map(item => <article key={item.id}><b>User</b><p>{item.input_text}</p><b>Expected</b><p>{item.expected_output}</p></article>)}</div>
      </> : <div className="empty"><TestTube2 size={38} /><p>Select or create a training dataset.</p></div>}</div>
    </div>
    <ErrorBox error={error || createDataset.error || createExample.error || examples.error} />
  </section>
}

function ToolsPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['tools'], queryFn: () => api<Tool[]>('/tools') })
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', execution_mode: 'client', method: 'POST', url: '', requires_approval: true })
  const create = useMutation({ mutationFn: () => api<Tool>('/tools', { method: 'POST', body: JSON.stringify({ ...form, transport: form.execution_mode === 'client' ? 'client' : 'http', input_schema: { type: 'object', properties: {} } }) }), onSuccess: () => { setOpen(false); queryClient.invalidateQueries({ queryKey: ['tools'] }) } })
  return <section className="panel">
    <PageHeader eyebrow="EXTERNAL ACTIONS" title="Tool registry" subtitle="Describe external backend actions. Client tools are returned to the caller; server tools call approved APIs." action={<button className="primary compact" onClick={() => setOpen(!open)}><Plus size={16} /> New tool</button>} />
    {open && <form className="form-grid create-box" onSubmit={e => { e.preventDefault(); create.mutate() }}><Field label="Tool name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /><Field label="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /><Select label="Execution" value={form.execution_mode} onChange={e => setForm({ ...form, execution_mode: e.target.value })}><option value="client">Caller backend executes</option><option value="server">Agents Morf calls API</option></Select><Select label="Method" value={form.method} onChange={e => setForm({ ...form, method: e.target.value })}><option>POST</option><option>GET</option><option>PUT</option><option>PATCH</option><option>DELETE</option></Select><Field label="Endpoint URL" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} /><button className="primary">Create tool</button></form>}
    <ErrorBox error={error || create.error} />
    <div className="table-wrap"><table><thead><tr><th>Tool</th><th>Execution</th><th>Endpoint</th><th>Approval</th><th>Status</th></tr></thead><tbody>{data.map(tool => <tr key={tool.id}><td><b>{tool.name}</b><small>{tool.description}</small></td><td>{tool.execution_mode}</td><td>{tool.url || 'Caller-defined'}</td><td>{tool.requires_approval ? 'Required' : 'Automatic'}</td><td>{tool.enabled ? 'Enabled' : 'Disabled'}</td></tr>)}</tbody></table></div>
  </section>
}

function FeedbackPage() {
  const { data = [], error } = useQuery({ queryKey: ['feedback'], queryFn: () => api<Feedback[]>('/feedback') })
  return <section className="panel">
    <PageHeader eyebrow="HUMAN REVIEW" title="Feedback" subtitle="Review agent outcomes before promoting corrections into curated training data." />
    <ErrorBox error={error} />
    <div className="table-wrap"><table><thead><tr><th>Rating</th><th>Category</th><th>Comment / correction</th><th>Agent</th><th>Status</th><th>Created</th></tr></thead><tbody>{data.map(item => <tr key={item.id}><td>{item.rating > 0 ? '👍 Positive' : item.rating < 0 ? '👎 Negative' : 'Neutral'}</td><td>{item.category}</td><td><b>{item.comment || 'No comment'}</b>{item.correction && <small>Correction: {item.correction}</small>}</td><td>{item.agent_id || '—'}</td><td>{item.promoted_to_training ? 'Promoted' : 'Needs review'}</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>
  </section>
}

function ProvidersPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['providers'], queryFn: () => api<Provider[]>('/providers') })
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', kind: 'ollama', base_url: 'http://ollama:11434', model: 'qwen2.5:7b', api_key: '', priority: 100 })
  const create = useMutation({ mutationFn: () => api<Provider>('/providers', { method: 'POST', body: JSON.stringify({ ...form, api_key: form.api_key || undefined }) }), onSuccess: () => { setOpen(false); queryClient.invalidateQueries({ queryKey: ['providers'] }) } })
  return <section className="panel">
    <PageHeader eyebrow="MODEL ROUTING" title="AI providers" subtitle="Use Ollama locally and cloud providers as fallback or for peak demand." action={<button className="primary compact" onClick={() => setOpen(!open)}><Plus size={16} /> New provider</button>} />
    {open && <form className="form-grid create-box" onSubmit={e => { e.preventDefault(); create.mutate() }}><Field label="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /><Select label="Adapter" value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}><option value="ollama">Ollama</option><option value="openai_compatible">OpenAI-compatible</option><option value="gemini">Gemini</option><option value="anthropic">Anthropic</option><option value="grok_build">Grok Build (optional)</option></Select><Field label="Base URL" value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} /><Field label="Model" value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} required /><Field label="API key" type="password" value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} /><button className="primary">Create provider</button></form>}
    <ErrorBox error={error || create.error} />
    <div className="table-wrap"><table><thead><tr><th>Name</th><th>Adapter</th><th>Model</th><th>Priority</th><th>Status</th></tr></thead><tbody>{data.map(item => <tr key={item.id}><td><b>{item.name}</b></td><td>{item.kind}</td><td>{item.model}</td><td>{item.priority}</td><td>{item.enabled ? 'Enabled' : 'Disabled'}</td></tr>)}</tbody></table></div>
  </section>
}

function ApiKeysPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['api-keys'], queryFn: () => api<ApiKey[]>('/api-keys') })
  const [name, setName] = useState('')
  const [secret, setSecret] = useState('')
  const create = useMutation({ mutationFn: () => api<ApiKeyCreated>('/api-keys', { method: 'POST', body: JSON.stringify({ name, scopes: ['chat:write', 'feedback:write'] }) }), onSuccess: result => { setSecret(result.key); setName(''); queryClient.invalidateQueries({ queryKey: ['api-keys'] }) } })
  return <section className="panel">
    <PageHeader eyebrow="INTEGRATION AUTH" title="API keys" subtitle="Keys let external products consume Agents Morf without sharing dashboard credentials." />
    <form className="inline-form" onSubmit={e => { e.preventDefault(); create.mutate() }}><input placeholder="Key name, e.g. ALLSENDER production" value={name} onChange={e => setName(e.target.value)} required /><button className="primary compact"><Plus size={16} /> Create key</button></form>
    {secret && <div className="secret-box"><b>Copy this key now. It will not be shown again.</b><code>{secret}</code><button className="secondary" onClick={() => navigator.clipboard.writeText(secret)}>Copy</button></div>}
    <ErrorBox error={error || create.error} />
    <div className="table-wrap"><table><thead><tr><th>Name</th><th>Prefix</th><th>Scopes</th><th>Last used</th><th>Status</th></tr></thead><tbody>{data.map(item => <tr key={item.id}><td><b>{item.name}</b></td><td><code>{item.prefix}…</code></td><td>{item.scopes.join(', ')}</td><td>{item.last_used_at ? new Date(item.last_used_at).toLocaleString() : 'Never'}</td><td>{item.revoked_at ? 'Revoked' : 'Active'}</td></tr>)}</tbody></table></div>
  </section>
}

function DocsPage() {
  const curl = useMemo(() => `curl -X POST https://agent.codemorf.tech/api/v1/chat/completions \\
  -H "Authorization: Bearer am_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"agent":"sales-agent","end_user_id":"customer-123","messages":[{"role":"user","content":"Hello"}]}'`, [])
  return <section className="panel">
    <PageHeader eyebrow="DEVELOPER EXPERIENCE" title="API documentation" subtitle="FastAPI publishes OpenAPI, Swagger UI and ReDoc automatically." />
    <div className="three"><a className="doc-card" href="/api/docs" target="_blank"><Braces size={28} /><b>Swagger UI</b><span>Interactive API reference</span></a><a className="doc-card" href="/api/redoc" target="_blank"><BookOpen size={28} /><b>ReDoc</b><span>Readable endpoint documentation</span></a><a className="doc-card" href="/api/openapi.json" target="_blank"><Activity size={28} /><b>OpenAPI JSON</b><span>Generate SDKs and integrations</span></a></div>
    <h3>OpenAI-compatible request</h3><pre>{curl}</pre>
  </section>
}

function SettingsPage() {
  return <section className="panel">
    <PageHeader eyebrow="PLATFORM BOUNDARY" title="Architecture settings" subtitle="Agents Morf is the AI control plane, not the operational backend of every product." />
    <div className="architecture-flow"><div>External products</div><span>→</span><div>Agents Morf API</div><span>→</span><div>Memory · RAG · Models · Tools</div><span>→</span><div>Structured response/tool call</div></div>
    <div className="three"><div><b>Safe Grok Build integration</b><p>The Grok Build source stays untouched. Agents Morf can optionally call its installed binary through a provider adapter.</p></div><div><b>No SMTP coupling</b><p>Email and messaging remain responsibilities of ALLSENDER or each external backend.</p></div><div><b>Training, not magic</b><p>Prompt versions, curated examples, memory, knowledge and evaluations train behavior. Fine-tuning can be added later.</p></div></div>
  </section>
}

function Protected() {
  if (!localStorage.getItem('access_token')) return <Navigate to="/login" replace />
  return <Layout><Routes>
    <Route path="/" element={<Overview />} />
    <Route path="/agents" element={<AgentsPage />} />
    <Route path="/studio" element={<StudioPage />} />
    <Route path="/memory" element={<MemoryPage />} />
    <Route path="/knowledge" element={<KnowledgePage />} />
    <Route path="/training" element={<TrainingPage />} />
    <Route path="/feedback" element={<FeedbackPage />} />
    <Route path="/tools" element={<ToolsPage />} />
    <Route path="/providers" element={<ProvidersPage />} />
    <Route path="/api-keys" element={<ApiKeysPage />} />
    <Route path="/docs" element={<DocsPage />} />
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="*" element={<Navigate to="/" />} />
  </Routes></Layout>
}

export default function App() {
  return <Routes><Route path="/login" element={<Login />} /><Route path="/*" element={<Protected />} /></Routes>
}
