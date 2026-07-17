const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type RequestOptions = RequestInit & { organizationId?: string }

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = localStorage.getItem('access_token')
  const organizationId = options.organizationId || localStorage.getItem('organization_id')
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (organizationId) headers.set('X-Organization-ID', organizationId)
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Request failed')
  }
  return response.json()
}

export type Dashboard = { agents: number; leads: number; reservations: number; orders: number; calls: number; conversations: number }
export type Organization = { id: string; name: string; slug: string; plan: string }
export type Agent = { id: string; name: string; description: string; system_prompt: string; model?: string; enabled: boolean }
export type Provider = { id: string; name: string; kind: string; model: string; enabled: boolean }
export type Lead = { id: string; name: string; email?: string; phone?: string; status: string; score: number }
export type Reservation = { id: string; customer_name: string; starts_at: string; party_size: number; status: string }
export type Order = { id: string; customer_name: string; total: string; currency: string; status: string }
