import { useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bot, CalendarDays, Gauge, LogOut, PackageCheck, PhoneCall, Settings, ShoppingBag, Sparkles, Users } from 'lucide-react'
import { Agent, Dashboard, Lead, Order, Organization, Provider, Reservation, api } from './api'

function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError('')
    try {
      const tokens = await api<{access_token:string}>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      localStorage.setItem('access_token', tokens.access_token)
      const organizations = await api<Organization[]>('/organizations')
      if (organizations[0]) localStorage.setItem('organization_id', organizations[0].id)
      navigate('/')
    } catch (err) { setError(err instanceof Error ? err.message : 'Login failed') }
  }
  return <main className="login-shell">
    <section className="login-card">
      <img src="/agents-morf-logo.png" className="login-logo" />
      <p className="eyebrow">AUTONOMOUS AI AGENT OPERATING SYSTEM</p>
      <h1>Command center</h1>
      <p className="muted">Operate sales, reservations, orders and customer conversations from one secure platform.</p>
      <form onSubmit={submit} className="stack">
        <label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></label>
        <label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required /></label>
        {error && <div className="error">{error}</div>}
        <button className="primary">Sign in</button>
      </form>
    </section>
  </main>
}

const nav = [
  ['/', 'Overview', Gauge], ['/agents', 'Agents', Bot], ['/leads', 'Sales leads', Users],
  ['/reservations', 'Reservations', CalendarDays], ['/orders', 'Orders', ShoppingBag],
  ['/calls', 'Call jobs', PhoneCall], ['/providers', 'AI providers', Sparkles], ['/settings', 'Settings', Settings],
] as const

function Layout({children}:{children:React.ReactNode}) {
  const navigate = useNavigate()
  return <div className="app-shell">
    <aside>
      <div className="brand"><img src="/agents-morf-logo.png"/><div><strong>Agents Morf</strong><small>CodeMorf AI Platform</small></div></div>
      <nav>{nav.map(([to,label,Icon])=><NavLink key={to} to={to} end={to==='/' }><Icon size={18}/>{label}</NavLink>)}</nav>
      <button className="logout" onClick={()=>{localStorage.clear();navigate('/login')}}><LogOut size={18}/> Sign out</button>
    </aside>
    <section className="workspace"><header><div><p className="eyebrow">AGENT.CODEMORF.TECH</p><h2>Autonomous operations</h2></div><span className="status"><i/> Platform online</span></header>{children}</section>
  </div>
}

function Overview() {
  const {data, error} = useQuery({queryKey:['dashboard'], queryFn:()=>api<Dashboard>('/dashboard')})
  const cards = data ? Object.entries(data) : []
  return <div><div className="hero"><div><p className="eyebrow">REAL-WORLD EXECUTION</p><h1>Agents that converse, decide and act.</h1><p>Monitor the business work delegated to your AI workforce.</p></div><Bot size={72}/></div>{error && <div className="error">{(error as Error).message}</div>}<div className="metric-grid">{cards.map(([k,v])=><article className="metric" key={k}><span>{k}</span><strong>{v}</strong></article>)}</div><section className="panel"><h3>Operating principles</h3><div className="three"><div><b>Human conversations</b><p>Natural, contextual and policy-aware.</p></div><div><b>Approved actions</b><p>Business tools execute through auditable APIs.</p></div><div><b>Provider freedom</b><p>Use cloud or local models without locking the platform.</p></div></div></section></div>
}

function TablePage<T>({title, queryKey, path, columns}:{title:string;queryKey:string;path:string;columns:[string,(row:T)=>React.ReactNode][]}) {
  const {data=[], error} = useQuery({queryKey:[queryKey], queryFn:()=>api<T[]>(path)})
  return <section className="panel"><div className="panel-head"><div><p className="eyebrow">OPERATIONS</p><h1>{title}</h1></div><span className="badge">{data.length} records</span></div>{error && <div className="error">{(error as Error).message}</div>}<div className="table-wrap"><table><thead><tr>{columns.map(([c])=><th key={c}>{c}</th>)}</tr></thead><tbody>{data.map((row,i)=><tr key={i}>{columns.map(([c,fn])=><td key={c}>{fn(row)}</td>)}</tr>)}</tbody></table></div></section>
}

function Agents(){return <TablePage<Agent> title="Agent workforce" queryKey="agents" path="/agents" columns={[["Name",r=><b>{r.name}</b>],["Description",r=>r.description||'—'],["Model",r=>r.model||'Provider default'],["Status",r=><span className="badge">{r.enabled?'Active':'Disabled'}</span>]]}/>} 
function Leads(){return <TablePage<Lead> title="Sales leads" queryKey="leads" path="/leads" columns={[["Lead",r=><b>{r.name}</b>],["Contact",r=>r.email||r.phone||'—'],["Status",r=>r.status],["Score",r=>r.score]]}/>} 
function Reservations(){return <TablePage<Reservation> title="Reservations" queryKey="reservations" path="/reservations" columns={[["Customer",r=><b>{r.customer_name}</b>],["Date",r=>new Date(r.starts_at).toLocaleString()],["Party",r=>r.party_size],["Status",r=>r.status]]}/>} 
function Orders(){return <TablePage<Order> title="Orders" queryKey="orders" path="/orders" columns={[["Customer",r=><b>{r.customer_name}</b>],["Total",r=>`${r.currency} ${r.total}`],["Status",r=>r.status]]}/>} 
function Providers(){return <TablePage<Provider> title="AI providers" queryKey="providers" path="/providers" columns={[["Name",r=><b>{r.name}</b>],["Adapter",r=>r.kind],["Model",r=>r.model],["Status",r=>r.enabled?'Enabled':'Disabled']]}/>} 
function Placeholder({title,children}:{title:string;children:string}){return <section className="panel"><PackageCheck size={36}/><h1>{title}</h1><p className="muted">{children}</p></section>}

function Protected() {
  if (!localStorage.getItem('access_token')) return <Navigate to="/login" replace />
  return <Layout><Routes><Route path="/" element={<Overview/>}/><Route path="/agents" element={<Agents/>}/><Route path="/leads" element={<Leads/>}/><Route path="/reservations" element={<Reservations/>}/><Route path="/orders" element={<Orders/>}/><Route path="/providers" element={<Providers/>}/><Route path="/calls" element={<Placeholder title="Call orchestration">Create call jobs through the API, then connect a telephony provider before executing real calls.</Placeholder>}/><Route path="/settings" element={<Placeholder title="Platform settings">Configure providers and SMTP2GO through protected backend settings and server environment variables.</Placeholder>}/><Route path="*" element={<Navigate to="/"/>}/></Routes></Layout>
}

export default function App(){return <Routes><Route path="/login" element={<Login/>}/><Route path="/*" element={<Protected/>}/></Routes>}
