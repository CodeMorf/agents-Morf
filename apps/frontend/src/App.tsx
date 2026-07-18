import { useEffect, useMemo, useState } from 'react'
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
  Users,
  Wrench,
  Moon,
  Sun,
  TerminalSquare,
} from 'lucide-react'
import { AgentsBuilderPage } from './agents-builder'
import { TerminalPage } from './terminal'
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
  ModelCatalog,
  Organization,
  Provider,
  Tool,
  TrainingDataset,
  TrainingExample,
  QuotaStatus,
  UsagePoint,
  UsageReport,
  api,
} from './api'
import { ChatWorkspace, useTheme } from './chat'

type Me = {
  id: string
  email: string
  full_name: string
  is_superuser: boolean
  role?: string | null
  organization_id?: string | null
  organization_name?: string | null
}

function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => api<Me>('/auth/me'),
    retry: false,
  })
}

/** Platform ops only — clients never see provider keys or LLM catalog management. */
function isPlatformAdmin(me?: Me | null) {
  return Boolean(me?.is_superuser)
}

function isOrgAdmin(me?: Me | null) {
  if (!me) return false
  if (me.is_superuser) return true
  return ['organization_owner', 'organization_admin', 'super_admin'].includes(me.role || '')
}

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
  const [loading, setLoading] = useState(false)
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = await api<{ access_token: string }>('/auth/login', {
        method: 'POST', body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      })
      localStorage.setItem('access_token', tokens.access_token)
      const organizations = await api<Organization[]>('/organizations')
      if (organizations[0]) localStorage.setItem('organization_id', organizations[0].id)
      navigate('/')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(
        msg.includes('502') || msg.includes('Bad Gateway') || msg.includes('Failed to fetch')
          ? 'No se pudo conectar con la API (502). El backend está reiniciando — espera 10s e intenta de nuevo.'
          : msg === 'Invalid email or password'
            ? 'Email o contraseña incorrectos. Usa las credenciales de Allsender actuales.'
            : msg,
      )
    } finally {
      setLoading(false)
    }
  }
  return <main className="login-shell">
    <section className="login-card">
      <img src="/agents-morf-logo.png" className="login-logo" alt="Agents Morf" />
      <p className="eyebrow">AUTONOMOUS AI AGENT OPERATING SYSTEM</p>
      <h1>Agent control plane</h1>
      <p className="muted">Build, train, test and expose autonomous agents through one secure API.</p>
      <form onSubmit={submit} className="stack">
        <Field label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="username" />
        <Field label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password" />
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={loading}>{loading ? 'Entrando…' : 'Sign in'}</button>
      </form>
      <p className="muted" style={{ marginTop: 12, textAlign: 'center' }}>
        <a href="/forgot-password" style={{ color: '#91a8b8' }}>¿Olvidaste tu contraseña?</a>
      </p>
      <p className="muted" style={{ marginTop: 8, textAlign: 'center' }}>
        ¿Empresa nueva? <a href="/register" style={{ color: '#35eddb' }}>Registrar organización</a>
      </p>
    </section>
  </main>
}

function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(''); setMessage(''); setToken('')
    try {
      const res = await api<{ message: string; reset_token?: string }>('/auth/forgot-password', {
        method: 'POST', body: JSON.stringify({ email }),
      })
      setMessage(res.message)
      if (res.reset_token) setToken(res.reset_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error')
    }
  }
  return <main className="login-shell"><section className="login-card">
    <p className="eyebrow">RECUPERACIÓN</p>
    <h1>Restablecer contraseña</h1>
    <p className="muted">Te emitiremos un token de un solo uso (en staging se muestra aquí porque aún no hay email SMTP).</p>
    <form onSubmit={submit} className="stack">
      <Field label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
      {error && <div className="error">{error}</div>}
      {message && <div className="secret-box"><b>{message}</b>{token && <><code>{token}</code><a className="primary compact" href={`/reset-password?token=${encodeURIComponent(token)}`}>Continuar</a></>}</div>}
      <button className="primary">Solicitar reset</button>
    </form>
    <p className="muted" style={{ marginTop: 16, textAlign: 'center' }}><a href="/login" style={{ color: '#35eddb' }}>Volver al login</a></p>
  </section></main>
}

function ResetPassword() {
  const navigate = useNavigate()
  const params = new URLSearchParams(window.location.search)
  const [token, setToken] = useState(params.get('token') || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState(false)
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError('')
    try {
      await api('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password }) })
      setOk(true)
      setTimeout(() => navigate('/login'), 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error')
    }
  }
  return <main className="login-shell"><section className="login-card">
    <p className="eyebrow">NUEVA CONTRASEÑA</p>
    <h1>Definir contraseña</h1>
    <form onSubmit={submit} className="stack">
      <Field label="Token" value={token} onChange={e => setToken(e.target.value)} required />
      <Field label="Nueva contraseña (mín. 12)" type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={12} />
      {error && <div className="error">{error}</div>}
      {ok && <div className="secret-box"><b>Contraseña actualizada. Redirigiendo al login…</b></div>}
      <button className="primary">Guardar</button>
    </form>
  </section></main>
}

function AcceptInvite() {
  const navigate = useNavigate()
  const params = new URLSearchParams(window.location.search)
  const [token, setToken] = useState(params.get('token') || '')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError('')
    try {
      const res = await api<{ access_token: string; organization: Organization }>('/auth/accept-invite', {
        method: 'POST', body: JSON.stringify({ token, password, full_name: fullName }),
      })
      localStorage.setItem('access_token', res.access_token)
      if (res.organization?.id) localStorage.setItem('organization_id', res.organization.id)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error')
    }
  }
  return <main className="login-shell"><section className="login-card">
    <p className="eyebrow">INVITACIÓN</p>
    <h1>Unirse a la organización</h1>
    <form onSubmit={submit} className="stack">
      <Field label="Token de invitación" value={token} onChange={e => setToken(e.target.value)} required />
      <Field label="Tu nombre" value={fullName} onChange={e => setFullName(e.target.value)} />
      <Field label="Contraseña (mín. 12)" type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={12} />
      {error && <div className="error">{error}</div>}
      <button className="primary">Aceptar invitación</button>
    </form>
  </section></main>
}

function Register() {
  const navigate = useNavigate()
  const { data: regStatus } = useQuery({
    queryKey: ['registration-status'],
    queryFn: () => api<{ allow_public_registration: boolean; default_plan: string }>('/auth/registration-status'),
  })
  const [form, setForm] = useState({
    organization_name: '',
    organization_slug: '',
    email: '',
    password: '',
    full_name: '',
  })
  const [error, setError] = useState('')
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const body: Record<string, string> = {
        organization_name: form.organization_name,
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        locale: 'es',
      }
      if (form.organization_slug.trim()) body.organization_slug = form.organization_slug.trim()
      const result = await api<{
        access_token: string
        organization: Organization
      }>('/auth/register', { method: 'POST', body: JSON.stringify(body) })
      localStorage.setItem('access_token', result.access_token)
      if (result.organization?.id) localStorage.setItem('organization_id', result.organization.id)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    }
  }
  if (regStatus && !regStatus.allow_public_registration) {
    return <main className="login-shell"><section className="login-card">
      <h1>Registro deshabilitado</h1>
      <p className="muted">El registro público está desactivado. Contacta al administrador.</p>
      <a className="primary" href="/login" style={{ display: 'inline-flex', marginTop: 16, textDecoration: 'none' }}>Volver al login</a>
    </section></main>
  }
  return <main className="login-shell">
    <section className="login-card" style={{ width: 'min(520px, 100%)' }}>
      <img src="/agents-morf-logo.png" className="login-logo" alt="Agents Morf" />
      <p className="eyebrow">FASE 2 · ONBOARDING</p>
      <h1>Registrar empresa</h1>
      <p className="muted">Crea tu organización y el primer usuario owner. Plan: {regStatus?.default_plan || 'trial'}.</p>
      <form onSubmit={submit} className="stack">
        <Field label="Nombre de la empresa" value={form.organization_name} onChange={e => setForm({
          ...form,
          organization_name: e.target.value,
          organization_slug: form.organization_slug || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
        })} required />
        <Field label="Slug (URL)" value={form.organization_slug} onChange={e => setForm({ ...form, organization_slug: e.target.value })} placeholder="mi-empresa" />
        <Field label="Tu nombre" value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} />
        <Field label="Email" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
        <Field label="Contraseña (mín. 12)" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required minLength={12} />
        {error && <div className="error">{error}</div>}
        <button className="primary">Crear organización</button>
      </form>
      <p className="muted" style={{ marginTop: 16, textAlign: 'center' }}>
        ¿Ya tienes cuenta? <a href="/login" style={{ color: '#35eddb' }}>Iniciar sesión</a>
      </p>
    </section>
  </main>
}

type NavItem = { to: string; label: string; icon: typeof Gauge; when?: 'always' | 'org_admin' | 'platform' }

const navItems: NavItem[] = [
  { to: '/', label: 'Chat', icon: MessagesSquare, when: 'always' },
  { to: '/agents', label: 'Agent Builder', icon: Bot, when: 'always' },
  { to: '/terminal', label: 'Morf Terminal', icon: TerminalSquare, when: 'always' },
  { to: '/docs', label: 'API Docs', icon: BookOpen, when: 'always' },
  { to: '/api-keys', label: 'API Keys', icon: KeyRound, when: 'org_admin' },
  { to: '/members', label: 'Equipo', icon: Users, when: 'org_admin' },
  { to: '/usage', label: 'Uso', icon: Activity, when: 'org_admin' },
  { to: '/knowledge', label: 'Knowledge', icon: Database, when: 'org_admin' },
  { to: '/feedback', label: 'Feedback', icon: MessageCircleWarning, when: 'org_admin' },
  { to: '/tools', label: 'Tools', icon: Wrench, when: 'org_admin' },
  { to: '/memory', label: 'Memory admin', icon: BrainCircuit, when: 'platform' },
  { to: '/training', label: 'Training', icon: TestTube2, when: 'platform' },
  { to: '/models', label: 'Modelos', icon: Sparkles, when: 'platform' },
  { to: '/providers', label: 'Providers', icon: Network, when: 'platform' },
  { to: '/playground', label: 'Playground', icon: Braces, when: 'platform' },
  { to: '/studio', label: 'Studio lab', icon: Gauge, when: 'platform' },
  { to: '/settings', label: 'Settings', icon: Settings, when: 'org_admin' },
]

function Layout({ children, fullBleed = false }: { children: React.ReactNode; fullBleed?: boolean }) {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const [theme, toggleTheme] = useTheme()
  const visible = navItems.filter(item => {
    if (item.when === 'platform') return isPlatformAdmin(me)
    if (item.when === 'org_admin') return isOrgAdmin(me)
    return true
  })
  const orgName = me?.organization_name || 'CodeMorf'
  const initials = (me?.email || 'AM').slice(0, 2).toUpperCase()
  return <div className={fullBleed ? 'app-shell chat-mode' : 'app-shell'}>
    <aside>
      <div className="brand">
        <div className="brand-logo-fallback" title="Agents Morf">AM</div>
        <div>
          <strong>Agents Morf</strong>
          <small>Autonomous AI OS</small>
        </div>
      </div>
      <div className="org-chip">
        <div>
          <small>Organización</small>
          <b>{orgName}</b>
        </div>
        <span style={{ color: 'var(--muted)' }}>⌄</span>
      </div>
      <nav>
        {visible.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === '/'}>
            <Icon size={18} />{label}
          </NavLink>
        ))}
      </nav>
      <div className="side-note">
        <b>Router dinámico activo</b><br />
        Groq para chat · Ollama solo tareas ligeras · Tool calls ejecutadas por el cliente.
      </div>
      <div className="aside-foot">
        <button type="button" className="theme-toggle" onClick={toggleTheme}>
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {theme === 'dark' ? 'Cambiar a claro' : 'Cambiar a oscuro'}
        </button>
        <div className="profile-card">
          <div className="avatar">{initials}</div>
          <div>
            <strong>{me?.email || 'usuario'}</strong>
            <small>{me?.is_superuser ? 'Super Admin' : (me?.role || 'member')}</small>
          </div>
        </div>
        <button className="logout" onClick={() => { localStorage.clear(); navigate('/login') }}>
          <LogOut size={18} /> Salir
        </button>
      </div>
    </aside>
    <section className={fullBleed ? 'workspace workspace-bleed' : 'workspace'}>
      {!fullBleed && (
        <header className="topbar-modern">
          <div>
            <p className="eyebrow">Workspace / {orgName}</p>
            <h2>{me?.is_superuser ? 'Platform control' : 'Espacio de trabajo'}</h2>
          </div>
          <div className="top-pills">
            <span className="status"><i /> API healthy</span>
            <span className="pill-soft">execution_mode=client</span>
          </div>
        </header>
      )}
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
  return <AgentsBuilderPage />
}

function MiniChart({ title, points }: { title: string; points?: UsagePoint[] }) {
  if (!points || points.length === 0) {
    return <article className="chart-card"><h4>{title}</h4><p className="muted">No hay datos suficientes</p></article>
  }
  const max = Math.max(...points.map(p => p.value), 1)
  const width = 320
  const height = 120
  const step = points.length > 1 ? width / (points.length - 1) : width
  const path = points.map((p, i) => {
    const x = i * step
    const y = height - (p.value / max) * (height - 12) - 6
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return <article className="chart-card">
    <h4>{title}</h4>
    <svg viewBox={`0 0 ${width} ${height}`} className="sparkline" role="img" aria-label={title}>
      <path d={path} fill="none" stroke="#35eddb" strokeWidth="2.5" />
      {points.map((p, i) => {
        const x = i * step
        const y = height - (p.value / max) * (height - 12) - 6
        return <circle key={p.date + i} cx={x} cy={y} r="3" fill="#2b8cff" />
      })}
    </svg>
    <div className="chart-footer"><span>{points[0]?.date}</span><span>{points[points.length - 1]?.date}</span></div>
  </article>
}

function ModelsPage() {
  const { data, error } = useQuery({ queryKey: ['models-catalog'], queryFn: () => api<ModelCatalog>('/dashboard/models') })
  return <section className="panel">
    <PageHeader eyebrow="MODEL CATALOG" title="Modelos" subtitle="Estado de proveedores cloud y locales. Las claves API nunca se muestran." />
    <ErrorBox error={error} />
    {data && <div className="chips" style={{ marginBottom: 16 }}>
      <span>Default: {data.default_provider} / {data.default_model}</span>
      <span>Local chat fallback: {data.allow_local_chat_fallback ? 'ON' : 'OFF'}</span>
    </div>}
    <div className="table-wrap"><table>
      <thead><tr>
        <th>Proveedor</th><th>Modelo</th><th>ID</th><th>Tipo</th><th>Estado</th><th>Salud</th>
        <th>Prioridad</th><th>Uso</th><th>Chat</th><th>Embed</th><th>Tools</th><th>Stream</th>
        <th>Contexto</th><th>Latencia</th><th>Errores</th><th>Última prueba</th><th>Rol</th>
      </tr></thead>
      <tbody>{(data?.models || []).map(m => <tr key={m.id}>
        <td><b>{m.provider}</b><small>{m.provider_kind}</small></td>
        <td>{m.name}</td>
        <td><code>{m.model_id}</code></td>
        <td>{m.type}</td>
        <td>{m.enabled ? 'enabled' : 'disabled'}</td>
        <td>{m.health}</td>
        <td>{m.priority}</td>
        <td>{m.usage_allowed ? 'yes' : 'no'}</td>
        <td>{m.chat_allowed ? 'yes' : 'no'}</td>
        <td>{m.embeddings_allowed ? 'yes' : 'no'}</td>
        <td>{m.tool_calling ? 'yes' : 'no'}</td>
        <td>{m.streaming ? 'yes' : 'no'}</td>
        <td>{m.max_context ?? '—'}</td>
        <td>{m.recent_latency_ms != null ? `${m.recent_latency_ms} ms` : '—'}</td>
        <td>{m.error_count ?? 0}</td>
        <td>{m.last_tested_at ? new Date(m.last_tested_at).toLocaleString() : '—'}</td>
        <td>{m.is_primary ? 'principal' : m.is_fallback ? 'fallback' : '—'}</td>
      </tr>)}</tbody>
    </table></div>
    <div className="card-grid" style={{ marginTop: 18 }}>
      {(data?.models || []).filter(m => m.type === 'local' || m.provider === 'Groq').map(m => (
        <article className="entity-card" key={`${m.id}-note`}>
          <div className="entity-title"><Sparkles size={22} /><div><h3>{m.provider}</h3><small>{m.model_id}</small></div></div>
          <p>{m.notes || '—'}</p>
          {m.type === 'local' && <div className="warning-banner">Modelo local de capacidad limitada. Solo para pruebas controladas y tareas en segundo plano.</div>}
          {m.provider === 'Groq' && <div className="chips"><span>Cloud</span><span>Studio principal</span><span>Credenciales: {m.credentials_configured ? 'configuradas' : 'faltan'}</span></div>}
        </article>
      ))}
    </div>
  </section>
}

function UsagePage() {
  const [days, setDays] = useState(14)
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const { data, error } = useQuery({
    queryKey: ['usage', days, provider, model],
    queryFn: () => {
      const params = new URLSearchParams({ days: String(days) })
      if (provider) params.set('provider', provider)
      if (model) params.set('model', model)
      return api<UsageReport>(`/dashboard/usage?${params}`)
    },
  })
  const s = data?.summary || {}
  return <section className="panel">
    <PageHeader eyebrow="ANALYTICS" title="Uso" subtitle="Métricas reales de chat, tokens, latencia y proveedores. Sin datos inventados." />
    <div className="studio-toolbar">
      <Select label="Período (días)" value={String(days)} onChange={e => setDays(Number(e.target.value))}>
        <option value="7">7</option><option value="14">14</option><option value="30">30</option><option value="90">90</option>
      </Select>
      <Field label="Proveedor" value={provider} onChange={e => setProvider(e.target.value)} placeholder="Groq" />
      <Field label="Modelo" value={model} onChange={e => setModel(e.target.value)} placeholder="llama-3.1-8b-instant" />
    </div>
    <ErrorBox error={error} />
    {data?.quota && <div className="create-box" style={{ marginBottom: 16 }}>
      <div className="chips">
        <span>Plan: {data.quota.plan}</span>
        <span>Cuotas: {data.quota.enabled ? 'activas' : 'desactivadas'}</span>
        {data.quota.exceeded?.length ? <span style={{ borderColor: '#a43e57' }}>Excedido: {data.quota.exceeded.join(', ')}</span> : <span>Dentro de cuota</span>}
        {data.quota.resets_at && <span>Reset: {new Date(data.quota.resets_at).toLocaleString()}</span>}
      </div>
      <div className="metric-grid" style={{ marginTop: 12 }}>
        <article className="metric"><span>Req hoy / límite</span><strong>{data.quota.used.requests_today} / {data.quota.quotas.requests_per_day}</strong></article>
        <article className="metric"><span>Tokens hoy / límite</span><strong>{data.quota.used.tokens_today} / {data.quota.quotas.tokens_per_day}</strong></article>
        <article className="metric"><span>Agentes</span><strong>{data.quota.used.agents_count} / {data.quota.quotas.max_agents}</strong></article>
        <article className="metric"><span>API keys</span><strong>{data.quota.used.api_keys_count} / {data.quota.quotas.max_api_keys}</strong></article>
      </div>
    </div>}
    {!data?.has_data && <div className="empty"><Activity size={40} /><p>{data?.message || 'No hay datos suficientes'}</p></div>}
    {data?.has_data && <>
      <div className="metric-grid">
        <article className="metric"><span>Solicitudes hoy</span><strong>{s.requests_today ?? 0}</strong></article>
        <article className="metric"><span>Chats activos 24h</span><strong>{s.chats_active_24h ?? 0}</strong></article>
        <article className="metric"><span>Tokens total</span><strong>{s.total_tokens ?? 0}</strong></article>
        <article className="metric"><span>Latencia media</span><strong>{s.avg_latency_ms != null ? `${s.avg_latency_ms} ms` : '—'}</strong></article>
        <article className="metric"><span>p50 / p95</span><strong>{s.p50_latency_ms != null ? `${Math.round(Number(s.p50_latency_ms))}/${Math.round(Number(s.p95_latency_ms ?? 0))}` : '—'}</strong></article>
        <article className="metric"><span>Errores</span><strong>{s.errors ?? 0}</strong></article>
        <article className="metric"><span>Fallbacks</span><strong>{s.fallbacks ?? 0}</strong></article>
        <article className="metric"><span>Tool calls</span><strong>{s.tool_calls ?? 0}</strong></article>
        <article className="metric"><span>Memoria creada</span><strong>{s.memory_items_created ?? 0}</strong></article>
        <article className="metric"><span>Proveedor principal</span><strong>{String(s.primary_provider || '—')}</strong></article>
      </div>
      <div className="chips" style={{ marginBottom: 12 }}>
        <span>Modelo principal: {String(s.primary_model || '—')}</span>
        <span>Costo estimado: {s.estimated_cost != null ? String(s.estimated_cost) : 'no configurado'}</span>
        <span>Cuota: {s.quota_configured != null ? String(s.quota_configured) : 'no configurada'}</span>
        <span>429: {s.errors_429 ?? 0}</span>
        <span>5xx: {s.errors_5xx ?? 0}</span>
      </div>
      <div className="chart-grid">
        <MiniChart title="Solicitudes / día" points={data.series.requests_per_day} />
        <MiniChart title="Chats / día" points={data.series.chats_per_day} />
        <MiniChart title="Tokens entrada" points={data.series.prompt_tokens_per_day} />
        <MiniChart title="Tokens salida" points={data.series.completion_tokens_per_day} />
        <MiniChart title="Latencia media" points={data.series.avg_latency_per_day} />
        <MiniChart title="Errores / día" points={data.series.errors_per_day} />
      </div>
      <div className="split" style={{ marginTop: 18 }}>
        <div className="panel" style={{ marginTop: 0 }}>
          <h3>Por proveedor</h3>
          <div className="table-wrap"><table><thead><tr><th>Proveedor</th><th>Requests</th></tr></thead><tbody>
            {(data.breakdowns.by_provider || []).map(item => <tr key={item.name}><td>{item.name}</td><td>{item.value}</td></tr>)}
          </tbody></table></div>
        </div>
        <div className="panel" style={{ marginTop: 0 }}>
          <h3>Por modelo</h3>
          <div className="table-wrap"><table><thead><tr><th>Modelo</th><th>Requests</th></tr></thead><tbody>
            {(data.breakdowns.by_model || []).map(item => <tr key={item.name}><td>{item.name}</td><td>{item.value}</td></tr>)}
          </tbody></table></div>
        </div>
      </div>
    </>}
  </section>
}

function StudioPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const { data: catalog } = useQuery({ queryKey: ['models-catalog'], queryFn: () => api<ModelCatalog>('/dashboard/models') })
  const [agentId, setAgentId] = useState('')
  const [endUserId, setEndUserId] = useState('demo-user')
  const [input, setInput] = useState('')
  const [forceLocal, setForceLocal] = useState(false)
  const [history, setHistory] = useState<Array<{ role: string; content: string }>>([])
  const [conversationId, setConversationId] = useState<string>()
  const [meta, setMeta] = useState<{
    provider?: string
    model?: string
    memory?: number
    knowledge?: number
    latency?: number
    requestId?: string
    fallback?: boolean
    tokens?: number
    errors?: string[]
  }>({})
  const [feedbackTarget, setFeedbackTarget] = useState<{ conversationId: string; messageId: string }>()
  const defaultModel = catalog?.default_model || 'llama-3.1-8b-instant'
  const defaultProvider = catalog?.default_provider || 'groq'
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
        body: JSON.stringify({
          agent_id: agentId || undefined,
          conversation_id: conversationId,
          end_user_id: endUserId || undefined,
          model: forceLocal ? undefined : defaultModel,
          messages,
          stream: false,
          remember: true,
          force_local: forceLocal || undefined,
        }),
      })
    },
    onSuccess: result => {
      const answer = result.choices[0].message
      setHistory(current => [...current, { role: 'user', content: input }, { role: 'assistant', content: answer.content || `[Tool call: ${answer.tool_calls.map(tool => tool.name).join(', ')}]` }])
      setConversationId(result.conversation_id)
      setFeedbackTarget({ conversationId: result.conversation_id, messageId: result.assistant_message_id })
      feedback.reset()
      setMeta({
        provider: result.provider,
        model: result.model,
        memory: result.memory_hits,
        knowledge: result.knowledge_hits,
        latency: result.latency_ms,
        requestId: result.request_id,
        fallback: result.fallback_used,
        tokens: result.usage?.total_tokens,
        errors: result.provider_errors,
      })
      setInput('')
    },
  })
  return <section className="panel studio">
    <PageHeader eyebrow="PLAYGROUND" title="Agent Studio" subtitle="Groq por defecto. Ollama no se usa para chat productivo." />
    <div className="chips" style={{ marginBottom: 12 }}>
      <span>Proveedor por defecto: {defaultProvider}</span>
      <span>Modelo por defecto: {defaultModel}</span>
      <span>Ollama chat: deshabilitado para usuarios normales</span>
    </div>
    {forceLocal && <div className="warning-banner">Modelo local de capacidad limitada. Solo para pruebas controladas y tareas en segundo plano. Solo super_admin.</div>}
    <div className="studio-toolbar">
      <Select label="Agent" value={agentId} onChange={e => setAgentId(e.target.value)}><option value="">Default active agent</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</Select>
      <Field label="External end-user ID" value={endUserId} onChange={e => setEndUserId(e.target.value)} />
      <label className="checkbox-row"><input type="checkbox" checked={forceLocal} onChange={e => setForceLocal(e.target.checked)} /> Forzar Ollama (super_admin)</label>
      <button className="secondary" onClick={() => { setHistory([]); setConversationId(undefined); setFeedbackTarget(undefined); setMeta({}) }}>New conversation</button>
    </div>
    <div className="chat-log">{history.length === 0 && <div className="empty"><MessagesSquare size={40} /><p>Start a conversation. Memory and knowledge hits will appear below.</p></div>}{history.map((item, index) => <div key={index} className={`bubble ${item.role}`}><b>{item.role}</b><p>{item.content}</p></div>)}</div>
    <ErrorBox error={send.error} />
    {!!meta.errors?.length && <div className="error">Provider errors: {meta.errors.join(' | ')}</div>}
    <form className="composer" onSubmit={e => { e.preventDefault(); if (input.trim()) send.mutate() }}><textarea value={input} onChange={e => setInput(e.target.value)} placeholder="Ask the agent..." /><button className="primary" disabled={send.isPending}>{send.isPending ? 'Thinking…' : 'Send'}</button></form>
    <div className="run-meta">
      <span>Provider: {meta.provider || '—'}</span>
      <span>Model: {meta.model || '—'}</span>
      <span>Latency: {meta.latency != null ? `${meta.latency} ms` : '—'}</span>
      <span>Request ID: {meta.requestId || '—'}</span>
      <span>Fallback: {meta.fallback ? 'yes' : 'no'}</span>
      <span>Tokens: {meta.tokens ?? 0}</span>
      <span>Memory hits: {meta.memory ?? 0}</span>
      <span>Knowledge hits: {meta.knowledge ?? 0}</span>
    </div>
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

const DEFAULT_SCOPES = ['chat:write', 'feedback:write', 'agents:read', 'memory:write', 'knowledge:read', '*'] as const

function ApiKeysPage() {
  const queryClient = useQueryClient()
  const { data = [], error } = useQuery({ queryKey: ['api-keys'], queryFn: () => api<ApiKey[]>('/api-keys') })
  const { data: scopeInfo } = useQuery({
    queryKey: ['api-key-scopes'],
    queryFn: () => api<{ scopes: string[]; descriptions: Record<string, string> }>('/api-keys/scopes'),
  })
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>(['chat:write', 'feedback:write'])
  const [secret, setSecret] = useState('')
  const available = scopeInfo?.scopes?.length ? scopeInfo.scopes : [...DEFAULT_SCOPES]
  const create = useMutation({
    mutationFn: () => api<ApiKeyCreated>('/api-keys', { method: 'POST', body: JSON.stringify({ name, scopes }) }),
    onSuccess: result => { setSecret(result.key); setName(''); queryClient.invalidateQueries({ queryKey: ['api-keys'] }) },
  })
  const revoke = useMutation({
    mutationFn: (id: string) => api<void>(`/api-keys/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys'] }),
  })
  function toggleScope(scope: string) {
    setScopes(current => current.includes(scope) ? current.filter(s => s !== scope) : [...current, scope])
  }
  return <section className="panel">
    <PageHeader eyebrow="INTEGRATION AUTH" title="API keys" subtitle="Crea, revoca y limita scopes. La key completa solo se muestra una vez." />
    <form className="stack create-box" onSubmit={e => { e.preventDefault(); create.mutate() }}>
      <Field label="Nombre de la key" value={name} onChange={e => setName(e.target.value)} placeholder="ALLSENDER production" required />
      <div>
        <p className="muted" style={{ marginBottom: 8 }}>Scopes</p>
        <div className="chips">
          {available.map(scope => (
            <button type="button" key={scope} className={scopes.includes(scope) ? 'chip-active' : ''} onClick={() => toggleScope(scope)} title={scopeInfo?.descriptions?.[scope] || scope}>
              {scopes.includes(scope) ? '✓ ' : ''}{scope}
            </button>
          ))}
        </div>
      </div>
      <button className="primary compact" disabled={!name || scopes.length === 0}><Plus size={16} /> Create key</button>
    </form>
    {secret && <div className="secret-box"><b>Copia esta key ahora. No se volverá a mostrar.</b><code>{secret}</code><button className="secondary" onClick={() => navigator.clipboard.writeText(secret)}>Copy</button></div>}
    <ErrorBox error={error || create.error || revoke.error} />
    <div className="table-wrap"><table><thead><tr><th>Name</th><th>Prefix</th><th>Scopes</th><th>Last used</th><th>Status</th><th></th></tr></thead><tbody>{data.map(item => <tr key={item.id}>
      <td><b>{item.name}</b></td>
      <td><code>{item.prefix}…</code></td>
      <td>{item.scopes.join(', ')}</td>
      <td>{item.last_used_at ? new Date(item.last_used_at).toLocaleString() : 'Never'}</td>
      <td>{item.revoked_at ? 'Revoked' : 'Active'}</td>
      <td>{!item.revoked_at && <button className="secondary compact" onClick={() => { if (confirm(`Revocar key ${item.name}?`)) revoke.mutate(item.id) }} disabled={revoke.isPending}>Revoke</button>}</td>
    </tr>)}</tbody></table></div>
  </section>
}

function PlaygroundPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: () => api<Agent[]>('/agents') })
  const [agentId, setAgentId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [message, setMessage] = useState('Hola, ¿quién eres?')
  const [endUserId, setEndUserId] = useState('playground-user')
  const [raw, setRaw] = useState('')
  const [meta, setMeta] = useState<{ provider?: string; model?: string; latency?: number; requestId?: string }>({})
  const [error, setError] = useState('')
  const send = useMutation({
    mutationFn: async () => {
      setError('')
      const selected = agents.find(a => a.id === agentId)
      const payload = {
        agent_id: agentId || undefined,
        agent: selected?.slug,
        end_user_id: endUserId || undefined,
        messages: [{ role: 'user', content: message }],
        stream: false,
        remember: false,
      }
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      const org = localStorage.getItem('organization_id')
      if (org) headers['X-Organization-ID'] = org
      if (apiKey.trim()) {
        headers.Authorization = `Bearer ${apiKey.trim()}`
      } else {
        const token = localStorage.getItem('access_token')
        if (token) headers.Authorization = `Bearer ${token}`
      }
      const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
      const response = await fetch(`${base}/chat/completions`, { method: 'POST', headers, body: JSON.stringify(payload) })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`)
      return body as ChatResponse
    },
    onSuccess: result => {
      setRaw(JSON.stringify(result, null, 2))
      setMeta({
        provider: result.provider,
        model: result.model,
        latency: result.latency_ms,
        requestId: result.request_id,
      })
    },
    onError: err => setError(err instanceof Error ? err.message : String(err)),
  })
  return <section className="panel">
    <PageHeader eyebrow="API PLAYGROUND" title="Playground seguro" subtitle="Prueba chat/completions como lo haría un backend de producto. No es una terminal del servidor." />
    <div className="warning-banner">Solo envía JSON a la API de Agents Morf. No hay shell, no hay acceso al VPS.</div>
    <div className="form-grid create-box">
      <Select label="Agent" value={agentId} onChange={e => setAgentId(e.target.value)}>
        <option value="">Default / first agent</option>
        {agents.map(a => <option key={a.id} value={a.id}>{a.name} ({a.slug})</option>)}
      </Select>
      <Field label="End-user ID" value={endUserId} onChange={e => setEndUserId(e.target.value)} />
      <Field label="API key (opcional, am_…)" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="Vacío = usa sesión del dashboard" />
      <Textarea label="Mensaje de usuario" value={message} onChange={e => setMessage(e.target.value)} required />
      <button className="primary" disabled={send.isPending || !message.trim()} onClick={() => send.mutate()}>{send.isPending ? 'Calling…' : 'Run request'}</button>
    </div>
    {error && <div className="error">{error}</div>}
    <div className="run-meta">
      <span>Provider: {meta.provider || '—'}</span>
      <span>Model: {meta.model || '—'}</span>
      <span>Latency: {meta.latency != null ? `${meta.latency} ms` : '—'}</span>
      <span>Request ID: {meta.requestId || '—'}</span>
    </div>
    <h3>Response JSON</h3>
    <pre>{raw || 'Ejecuta una petición para ver la respuesta.'}</pre>
  </section>
}

function DocsPage() {
  const base = typeof window !== 'undefined' ? window.location.origin : 'https://agent.codemorf.tech'
  const curl = useMemo(() => `curl -X POST ${base}/api/v1/chat/completions \\
  -H "Authorization: Bearer am_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent": "mi-agente-slug",
    "end_user_id": "customer-123",
    "messages": [{"role": "user", "content": "Hola"}]
  }'`, [base])
  const python = useMemo(() => `import requests

url = "${base}/api/v1/chat/completions"
headers = {
    "Authorization": "Bearer am_YOUR_KEY",
    "Content-Type": "application/json",
}
payload = {
    "agent": "mi-agente-slug",
    "end_user_id": "customer-123",
    "messages": [{"role": "user", "content": "Hola"}],
}
r = requests.post(url, json=payload, headers=headers, timeout=60)
print(r.status_code, r.json())`, [base])
  const javascript = useMemo(() => `const res = await fetch("${base}/api/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer am_YOUR_KEY",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    agent: "mi-agente-slug",
    end_user_id: "customer-123",
    messages: [{ role: "user", content: "Hola" }],
  }),
});
const data = await res.json();
console.log(data.provider, data.model, data.choices?.[0]?.message?.content);`, [base])
  const toolResult = useMemo(() => `curl -X POST ${base}/api/v1/tool-results \\
  -H "Authorization: Bearer am_YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "conversation_id": "UUID",
    "tool_call_id": "call_123",
    "status": "success",
    "result": {"available": true, "slots": ["19:00", "20:30"]},
    "idempotency_key": "unique-action-key"
  }'`, [base])
  const installTpl = useMemo(() => `curl -X POST ${base}/api/v1/agent-templates/sales-ai/install \\
  -H "Authorization: Bearer YOUR_JWT" \\
  -H "X-Organization-ID: ORG_UUID" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Mi Venta AI"}'`, [base])
  return <section className="panel">
    <PageHeader eyebrow="DEVELOPER EXPERIENCE" title="API documentation" subtitle="OpenAPI vivo + Agent Builder + tool_results + ejemplos listos para integrar." />
    <div className="three">
      <a className="doc-card" href="/api/docs" target="_blank" rel="noreferrer"><Braces size={28} /><b>Swagger UI</b><span>Interactive API reference</span></a>
      <a className="doc-card" href="/api/redoc" target="_blank" rel="noreferrer"><BookOpen size={28} /><b>ReDoc</b><span>Readable endpoint documentation</span></a>
      <a className="doc-card" href="/api/openapi.json" target="_blank" rel="noreferrer"><Activity size={28} /><b>OpenAPI JSON</b><span>Generate SDKs and integrations</span></a>
    </div>

    <div className="create-box" style={{ marginTop: 18 }}>
      <h3 style={{ marginTop: 0 }}>Agent Builder (UI + API)</h3>
      <p className="muted">
        Ruta UI: <a href="/agents"><code>/agents</code></a> · Terminal playground: <a href="/terminal"><code>/terminal</code></a> (no es shell Linux).
        Agents Morf razona y devuelve <code>tool_calls</code>; el backend del cliente ejecuta y responde con <code>tool-results</code>.
      </p>
      <div className="chips" style={{ margin: '12px 0' }}>
        <span>execution_mode=client</span>
        <span>10 plantillas oficiales</span>
        <span>versionado inmutable</span>
        <span>sin secretos en manifiestos</span>
      </div>
      <div className="table-wrap"><table>
        <thead><tr><th>Método</th><th>Endpoint</th><th>Uso</th></tr></thead>
        <tbody>
          <tr><td>GET</td><td><code>/api/v1/agent-templates</code></td><td>Listar 10 plantillas globales</td></tr>
          <tr><td>GET</td><td><code>/api/v1/agent-templates/&#123;slug&#125;</code></td><td>Detalle + tools + prompts</td></tr>
          <tr><td>POST</td><td><code>/api/v1/agent-templates/&#123;slug&#125;/install</code></td><td>Copia draft tenant-owned</td></tr>
          <tr><td>GET/POST/PATCH</td><td><code>/api/v1/agents</code></td><td>CRUD agentes</td></tr>
          <tr><td>POST</td><td><code>/api/v1/agents/&#123;id&#125;/publish</code></td><td>Versión inmutable</td></tr>
          <tr><td>GET</td><td><code>/api/v1/agents/&#123;id&#125;/versions</code></td><td>Historial</td></tr>
          <tr><td>POST</td><td><code>/api/v1/agents/&#123;id&#125;/versions/&#123;n&#125;/restore</code></td><td>Rollback a draft</td></tr>
          <tr><td>GET</td><td><code>/api/v1/agents/&#123;id&#125;/integration-manifest</code></td><td>curl/Python/JS sin secretos</td></tr>
          <tr><td>POST</td><td><code>/api/v1/tool-results</code></td><td>Continuar tras tool_call cliente</td></tr>
          <tr><td>POST</td><td><code>/api/v1/chat/completions</code></td><td>Chat OpenAI-compatible</td></tr>
        </tbody>
      </table></div>
    </div>

    <div className="create-box">
      <h3 style={{ marginTop: 0 }}>Catálogo de plantillas oficiales</h3>
      <div className="table-wrap"><table>
        <thead><tr><th>Nombre</th><th>Slug</th><th>Notas</th></tr></thead>
        <tbody>
          <tr><td>Venta AI</td><td><code>sales-ai</code></td><td>Leads, cotización, pedido (client tools)</td></tr>
          <tr><td>RestaApp AI</td><td><code>restaapp-ai</code></td><td>Menú/reservas; sin tablas en Morf</td></tr>
          <tr><td>Chatbot de soporte</td><td><code>support-chatbot</code></td><td>RAG + tickets</td></tr>
          <tr><td>Sucursales AI</td><td><code>branches-ai</code></td><td>Ubicaciones y citas</td></tr>
          <tr><td>Chatbot básico</td><td><code>basic-chatbot</code></td><td>FAQ; memoria off</td></tr>
          <tr><td>Programación AI</td><td><code>programming-ai</code></td><td>Patches vía runner cliente; sin shell VPS</td></tr>
          <tr><td>Análisis de datos AI</td><td><code>data-analysis-ai</code></td><td>SQL read-only</td></tr>
          <tr><td>Finanzas AI</td><td><code>finance-ai</code></td><td>Sin pagos/transferencias</td></tr>
          <tr><td>Auto Calendario AI</td><td><code>auto-calendar-ai</code></td><td>Idempotencia + timezone</td></tr>
          <tr><td>Departamento AI</td><td><code>department-ai</code></td><td>Perfil de dpto. al instalar</td></tr>
        </tbody>
      </table></div>
      <p className="muted">Flujo: plantilla global → install → draft → prueba en Terminal → publish. “Preentrenado” = prompts/tools/guardrails/ejemplos, no fine-tuning de pesos.</p>
    </div>

    <div className="create-box">
      <h3 style={{ marginTop: 0 }}>Tools de plataforma (todos los agentes)</h3>
      <p className="muted">Se ejecutan en Agents Morf — no requieren backend del cliente:</p>
      <div className="chips">
        <span>platform.web_search</span>
        <span>platform.fetch_url</span>
        <span>platform.search_knowledge</span>
        <span>platform.recall_memory</span>
        <span>platform.current_datetime</span>
        <span>platform.calculate</span>
        <span>platform.summarize_capabilities</span>
      </div>
      <p className="muted" style={{ marginTop: 10 }}>
        En el chat del panel (<code>runtime=studio</code>) el agente puede buscar en la web y leer páginas HTTPS públicas.
      </p>
    </div>
    <div className="chips" style={{ margin: '16px 0' }}>
      <span>Auth: Bearer am_… (API key) o JWT de dashboard</span>
      <span>Header opcional: X-Organization-ID</span>
      <span>Chat: POST /api/v1/chat/completions</span>
      <span>Tools: POST /api/v1/tool-results</span>
    </div>
    <h3>Instalar plantilla (dashboard JWT)</h3><pre>{installTpl}</pre>
    <h3>Chat completions (cURL)</h3><pre>{curl}</pre>
    <h3>Python</h3><pre>{python}</pre>
    <h3>JavaScript</h3><pre>{javascript}</pre>
    <h3>Tool result continuation (cliente ejecuta y devuelve)</h3>
    <pre>{toolResult}</pre>
    <p className="muted">Cuando <code>finish_reason=tool_calls</code>, el backend del cliente ejecuta la herramienta y llama a <code>/tool-results</code>. Agents Morf continúa y solo confirma acciones con status success.</p>
    <h3>Scopes de API key</h3>
    <div className="table-wrap"><table><thead><tr><th>Scope</th><th>Uso</th></tr></thead><tbody>
      <tr><td><code>chat:write</code></td><td>Chat completions</td></tr>
      <tr><td><code>tools:result</code></td><td>Postear tool_results (alias de chat:write)</td></tr>
      <tr><td><code>feedback:write</code></td><td>Feedback de respuestas</td></tr>
      <tr><td><code>agents:read</code></td><td>Leer agentes</td></tr>
      <tr><td><code>memory:write</code></td><td>Escribir memoria</td></tr>
      <tr><td><code>knowledge:read</code></td><td>Leer knowledge</td></tr>
      <tr><td><code>*</code></td><td>Acceso total (solo backends de confianza)</td></tr>
    </tbody></table></div>
    <h3>Documentación en repo</h3>
    <ul className="tool-list">
      <li><code>docs/AGENT_BUILDER.md</code></li>
      <li><code>docs/AGENT_TEMPLATES.md</code></li>
      <li><code>docs/AGENTS_MORF_TERMINAL.md</code></li>
      <li><code>docs/CLIENT_TOOL_EXECUTION.md</code></li>
      <li><code>docs/TOOL_RESULT_CONTINUATION.md</code></li>
      <li><code>docs/INTEGRATION_MANIFEST.md</code></li>
    </ul>
  </section>
}

type Member = {
  membership_id: string
  user_id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  created_at: string
}
type Invite = {
  id: string
  email: string
  role: string
  expires_at: string
  invite_token?: string | null
}

function MembersPage() {
  const queryClient = useQueryClient()
  const { data: members = [], error } = useQuery({ queryKey: ['members'], queryFn: () => api<Member[]>('/members') })
  const { data: invites = [] } = useQuery({ queryKey: ['invites'], queryFn: () => api<Invite[]>('/members/invites') })
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('developer')
  const [fullName, setFullName] = useState('')
  const [lastToken, setLastToken] = useState('')
  const invite = useMutation({
    mutationFn: () => api<Invite>('/members/invites', { method: 'POST', body: JSON.stringify({ email, role, full_name: fullName }) }),
    onSuccess: res => {
      setLastToken(res.invite_token || '')
      setEmail(''); setFullName('')
      queryClient.invalidateQueries({ queryKey: ['invites'] })
    },
  })
  const revokeInvite = useMutation({
    mutationFn: (id: string) => api<void>(`/members/invites/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['invites'] }),
  })
  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => api<Member>(`/members/${id}`, { method: 'PATCH', body: JSON.stringify({ role }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['members'] }),
  })
  const remove = useMutation({
    mutationFn: (id: string) => api<void>(`/members/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['members'] }),
  })
  return <section className="panel">
    <PageHeader eyebrow="ORGANIZATION" title="Members & invites" subtitle="Invita usuarios, asigna roles y revoca accesos. Sin shell del servidor." />
    <form className="form-grid create-box" onSubmit={e => { e.preventDefault(); invite.mutate() }}>
      <Field label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
      <Field label="Nombre" value={fullName} onChange={e => setFullName(e.target.value)} />
      <Select label="Rol" value={role} onChange={e => setRole(e.target.value)}>
        <option value="organization_admin">organization_admin</option>
        <option value="developer">developer</option>
        <option value="operator">operator</option>
        <option value="viewer">viewer</option>
      </Select>
      <button className="primary compact"><Plus size={16} /> Invitar</button>
    </form>
    {lastToken && <div className="secret-box">
      <b>Token de invitación (staging — cópialo ahora)</b>
      <code>{lastToken}</code>
      <a className="secondary compact" href={`/accept-invite?token=${encodeURIComponent(lastToken)}`}>Abrir aceptación</a>
    </div>}
    <ErrorBox error={error || invite.error || revokeInvite.error || changeRole.error || remove.error} />
    <h3>Miembros</h3>
    <div className="table-wrap"><table><thead><tr><th>Email</th><th>Nombre</th><th>Rol</th><th>Estado</th><th></th></tr></thead><tbody>
      {members.map(m => <tr key={m.membership_id}>
        <td><b>{m.email}</b></td>
        <td>{m.full_name || '—'}</td>
        <td>
          <select value={m.role} onChange={e => changeRole.mutate({ id: m.membership_id, role: e.target.value })}>
            <option value="organization_owner">organization_owner</option>
            <option value="organization_admin">organization_admin</option>
            <option value="developer">developer</option>
            <option value="operator">operator</option>
            <option value="viewer">viewer</option>
          </select>
        </td>
        <td>{m.is_active ? 'active' : 'inactive'}</td>
        <td><button className="secondary compact" onClick={() => { if (confirm(`Quitar a ${m.email}?`)) remove.mutate(m.membership_id) }}>Remove</button></td>
      </tr>)}
    </tbody></table></div>
    <h3 style={{ marginTop: 24 }}>Invitaciones pendientes</h3>
    <div className="table-wrap"><table><thead><tr><th>Email</th><th>Rol</th><th>Expira</th><th></th></tr></thead><tbody>
      {invites.map(i => <tr key={i.id}>
        <td>{i.email}</td>
        <td>{i.role}</td>
        <td>{new Date(i.expires_at).toLocaleString()}</td>
        <td><button className="secondary compact" onClick={() => revokeInvite.mutate(i.id)}>Revoke</button></td>
      </tr>)}
      {invites.length === 0 && <tr><td colSpan={4} className="muted">No hay invitaciones abiertas</td></tr>}
    </tbody></table></div>
  </section>
}

function SettingsPage() {
  const queryClient = useQueryClient()
  const { data: me } = useMe()
  const platform = isPlatformAdmin(me)
  const { data, error } = useQuery({
    queryKey: ['org-current'],
    queryFn: () => api<{ organization: Organization & { plan: string }; quota: QuotaStatus; plan_defaults: Record<string, unknown> }>('/organizations/current'),
  })
  const [form, setForm] = useState({ plan: 'trial', requests_per_day: 200, tokens_per_day: 100000, max_agents: 5, max_api_keys: 3, enabled: true })
  useEffect(() => {
    if (!data?.quota) return
    setForm({
      plan: data.quota.plan || 'trial',
      requests_per_day: data.quota.quotas.requests_per_day,
      tokens_per_day: data.quota.quotas.tokens_per_day,
      max_agents: data.quota.quotas.max_agents,
      max_api_keys: data.quota.quotas.max_api_keys,
      enabled: data.quota.enabled,
    })
  }, [data])
  const save = useMutation({
    mutationFn: () => api<QuotaStatus>('/organizations/current/quota', {
      method: 'PATCH',
      body: JSON.stringify(form),
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['org-current'] }); queryClient.invalidateQueries({ queryKey: ['usage'] }) },
  })
  const q = data?.quota
  return <section className="panel">
    <PageHeader
      eyebrow="ORGANIZACIÓN"
      title="Settings"
      subtitle={platform
        ? 'Solo super admin de plataforma puede asignar planes y cuotas a clientes.'
        : 'Tu plan y límites los define CodeMorf. Aquí solo ves el uso y el plan asignado.'}
    />
    <ErrorBox error={error || save.error} />
    {data && <div className="create-box">
      <p className="muted">Organización: <b>{data.organization.name}</b> · slug <code>{data.organization.slug}</code></p>
      {!platform && q && (
        <>
          <div className="warning-banner">
            El plan y las cuotas los gestiona la plataforma. Si necesitas más capacidad, contacta a CodeMorf.
          </div>
          <div className="metric-grid">
            <article className="metric"><span>Plan asignado</span><strong>{q.plan}</strong></article>
            <article className="metric"><span>Req / día</span><strong>{q.used.requests_today} / {q.quotas.requests_per_day}</strong></article>
            <article className="metric"><span>Tokens / día</span><strong>{q.used.tokens_today} / {q.quotas.tokens_per_day}</strong></article>
            <article className="metric"><span>Agentes</span><strong>{q.used.agents_count} / {q.quotas.max_agents}</strong></article>
            <article className="metric"><span>API keys</span><strong>{q.used.api_keys_count} / {q.quotas.max_api_keys}</strong></article>
          </div>
          <div className="chips" style={{ marginTop: 12 }}>
            <span>Restante hoy: {q.remaining?.requests_today ?? '—'} requests</span>
            {q.resets_at && <span>Reinicio cuota: {new Date(q.resets_at).toLocaleString()}</span>}
          </div>
        </>
      )}
      {platform && (
        <form className="form-grid" onSubmit={e => { e.preventDefault(); save.mutate() }}>
          <p className="muted" style={{ gridColumn: '1 / -1' }}>Editor de plataforma (super_admin). Los clientes no ven este formulario.</p>
          <Select label="Plan" value={form.plan} onChange={e => setForm({ ...form, plan: e.target.value })}>
            <option value="trial">trial</option>
            <option value="starter">starter</option>
            <option value="pro">pro</option>
            <option value="enterprise">enterprise</option>
          </Select>
          <label className="checkbox-row"><input type="checkbox" checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })} /> Cuotas activas</label>
          <Field label="Requests / día" type="number" value={form.requests_per_day} onChange={e => setForm({ ...form, requests_per_day: Number(e.target.value) })} />
          <Field label="Tokens / día" type="number" value={form.tokens_per_day} onChange={e => setForm({ ...form, tokens_per_day: Number(e.target.value) })} />
          <Field label="Max agents" type="number" value={form.max_agents} onChange={e => setForm({ ...form, max_agents: Number(e.target.value) })} />
          <Field label="Max API keys" type="number" value={form.max_api_keys} onChange={e => setForm({ ...form, max_api_keys: Number(e.target.value) })} />
          <button className="primary compact" disabled={save.isPending}>{save.isPending ? 'Guardando…' : 'Guardar cuotas (plataforma)'}</button>
        </form>
      )}
    </div>}
    <div className="architecture-flow" style={{ marginTop: 20 }}><div>Cliente</div><span>→</span><div>Agents Morf</div><span>→</span><div>Plan fijado por CodeMorf</div><span>→</span><div>Groq en backend</div></div>
  </section>
}

function PlatformOnly({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading } = useMe()
  if (isLoading) return <div className="panel">Cargando…</div>
  if (!isPlatformAdmin(me)) return <Navigate to="/" replace />
  return <>{children}</>
}

function OrgAdminOnly({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading } = useMe()
  if (isLoading) return <div className="panel">Cargando…</div>
  if (!isOrgAdmin(me)) return <Navigate to="/" replace />
  return <>{children}</>
}

function Protected() {
  if (!localStorage.getItem('access_token')) return <Navigate to="/login" replace />
  return (
    <Routes>
      <Route path="/" element={<Layout fullBleed><ChatWorkspace /></Layout>} />
      <Route path="/agents" element={<Layout><AgentsPage /></Layout>} />
      <Route path="/terminal" element={<Layout><TerminalPage /></Layout>} />
      <Route path="/docs" element={<Layout><DocsPage /></Layout>} />
      <Route path="/api-keys" element={<Layout><OrgAdminOnly><ApiKeysPage /></OrgAdminOnly></Layout>} />
      <Route path="/members" element={<Layout><OrgAdminOnly><MembersPage /></OrgAdminOnly></Layout>} />
      <Route path="/usage" element={<Layout><OrgAdminOnly><UsagePage /></OrgAdminOnly></Layout>} />
      <Route path="/knowledge" element={<Layout><OrgAdminOnly><KnowledgePage /></OrgAdminOnly></Layout>} />
      <Route path="/memory" element={<Layout><PlatformOnly><MemoryPage /></PlatformOnly></Layout>} />
      <Route path="/training" element={<Layout><PlatformOnly><TrainingPage /></PlatformOnly></Layout>} />
      <Route path="/feedback" element={<Layout><OrgAdminOnly><FeedbackPage /></OrgAdminOnly></Layout>} />
      <Route path="/tools" element={<Layout><OrgAdminOnly><ToolsPage /></OrgAdminOnly></Layout>} />
      <Route path="/settings" element={<Layout><OrgAdminOnly><SettingsPage /></OrgAdminOnly></Layout>} />
      <Route path="/models" element={<Layout><PlatformOnly><ModelsPage /></PlatformOnly></Layout>} />
      <Route path="/providers" element={<Layout><PlatformOnly><ProvidersPage /></PlatformOnly></Layout>} />
      <Route path="/playground" element={<Layout><PlatformOnly><PlaygroundPage /></PlatformOnly></Layout>} />
      <Route path="/studio" element={<Layout><PlatformOnly><StudioPage /></PlatformOnly></Layout>} />
      <Route path="/overview" element={<Layout><Overview /></Layout>} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}

export default function App() {
  return <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/register" element={<Register />} />
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/accept-invite" element={<AcceptInvite />} />
    <Route path="/*" element={<Protected />} />
  </Routes>
}
