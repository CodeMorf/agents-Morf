const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

type RequestOptions = RequestInit & { organizationId?: string }

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = localStorage.getItem('access_token')
  const organizationId = options.organizationId || localStorage.getItem('organization_id')
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (organizationId) headers.set('X-Organization-ID', organizationId)
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || body.message || 'Request failed')
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export type Dashboard = {
  agents: number
  providers: number
  tools: number
  knowledge_bases: number
  memories: number
  training_datasets: number
  conversations: number
  api_keys: number
  tokens: number
}

export type Organization = { id: string; name: string; slug: string; plan: string }

export type Agent = {
  id: string
  name: string
  slug: string
  description: string
  system_prompt: string
  instructions: string
  provider_id?: string
  model?: string
  temperature: string
  max_tokens: number
  enabled: boolean
  memory_enabled: boolean
  memory_top_k: number
  knowledge_enabled: boolean
  auto_tool_execution: boolean
  tool_approval_mode: string
  current_version: number
}

export type Provider = {
  id: string
  name: string
  kind: string
  base_url: string
  model: string
  enabled: boolean
  priority: number
}

export type Tool = {
  id: string
  name: string
  description: string
  transport: string
  execution_mode: string
  method: string
  url: string
  input_schema: Record<string, unknown>
  requires_approval: boolean
  enabled: boolean
}

export type MemoryItem = {
  id: string
  agent_id?: string
  conversation_id?: string
  end_user_id?: string
  scope: string
  kind: string
  key: string
  content: string
  importance: number
  tags: string[]
  source: string
  active: boolean
  created_at: string
}

export type KnowledgeBase = {
  id: string
  name: string
  description: string
  enabled: boolean
  created_at: string
}

export type Document = {
  id: string
  knowledge_base_id: string
  title: string
  source_type: string
  mime_type: string
  status: string
  chunk_count: number
  error: string
  created_at: string
}

export type TrainingDataset = {
  id: string
  name: string
  description: string
  status: string
  created_at: string
}

export type TrainingExample = {
  id: string
  dataset_id: string
  agent_id?: string
  input_text: string
  expected_output: string
  context: string
  tags: string[]
  weight: number
  enabled: boolean
}

export type Feedback = {
  id: string
  agent_id?: string
  conversation_id?: string
  message_id?: string
  end_user_id?: string
  rating: number
  category: string
  comment: string
  correction: string
  source: string
  promoted_to_training: boolean
  created_at: string
}

export type ApiKey = {
  id: string
  name: string
  prefix: string
  scopes: string[]
  last_used_at?: string
  expires_at?: string
  revoked_at?: string
  created_at: string
}

export type ApiKeyCreated = ApiKey & { key: string }

export type ToolCall = {
  id: string
  name: string
  arguments: Record<string, unknown>
  execution_mode: string
  requires_approval: boolean
  status: string
}

export type ChatResponse = {
  id: string
  model: string
  provider: string
  conversation_id: string
  assistant_message_id: string
  choices: Array<{
    message: { role: string; content: string; tool_calls: ToolCall[] }
    finish_reason: string
  }>
  usage: Record<string, number>
  memory_hits: number
  knowledge_hits: number
  request_id: string
  latency_ms?: number
  fallback_used?: boolean
  provider_errors?: string[]
}

export type ModelCatalogItem = {
  id: string
  provider: string
  provider_kind: string
  name: string
  model_id: string
  type: 'cloud' | 'local'
  enabled: boolean
  health: string
  priority: number
  usage_allowed: boolean
  allowed_tasks: string[]
  chat_allowed: boolean
  embeddings_allowed: boolean
  tool_calling: boolean
  streaming: boolean
  max_context?: number | null
  recent_latency_ms?: number | null
  error_count?: number
  request_count?: number
  last_tested_at?: string | null
  is_primary?: boolean
  is_fallback?: boolean
  credentials_configured?: boolean
  notes?: string
  local_policy?: Record<string, unknown>
}

export type ModelCatalog = {
  default_provider: string
  default_model: string
  allow_local_chat_fallback: boolean
  models: ModelCatalogItem[]
}

export type UsagePoint = { date: string; value: number }
export type UsageNamed = { name: string; value: number }

export type UsageReport = {
  has_data: boolean
  message?: string | null
  period_days: number
  summary: Record<string, number | string | null | undefined>
  series: Record<string, UsagePoint[]>
  breakdowns: {
    by_provider?: UsageNamed[]
    by_model?: UsageNamed[]
  }
}
