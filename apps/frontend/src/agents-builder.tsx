import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Bot,
  Check,
  Copy,
  Eye,
  Layers,
  Plus,
  Save,
  Sparkles,
  Upload,
} from 'lucide-react'
import { Agent, api } from './api'

export type AgentTemplateCard = {
  id: string
  slug: string
  name: string
  description: string
  category: string
  icon: string
  complexity: string
  languages: string[]
  version: string
  status: string
  memory_enabled: boolean
  knowledge_enabled: boolean
  tools_count: number
  required_tools: string[]
  changelog: string
}

type TemplateDetail = AgentTemplateCard & {
  definition: {
    system_prompt?: string
    instructions?: string
    tools?: Array<{ name: string; description?: string; requires_approval?: boolean }>
    memory_scopes?: string[]
    guardrails?: string[]
    examples?: Array<{ input: string; expected: string }>
    evaluation?: { checks?: string[]; min_score?: number }
    recommended_model_profile?: string
    routing_profile?: string
    department_profiles?: string[]
  }
  scope?: string
  checksum?: string
}

type WizardState = {
  name: string
  slug: string
  description: string
  language: string
  tone: string
  personality: string
  system_prompt: string
  instructions: string
  limits: string
  escalation: string
  model_mode: string
  memory_enabled: boolean
  knowledge_enabled: boolean
  tools_note: string
}

const emptyWizard = (): WizardState => ({
  name: '',
  slug: '',
  description: '',
  language: 'es',
  tone: 'profesional',
  personality: 'claro y orientado a acción',
  system_prompt: 'Eres un agente operativo de Agents Morf. Razonas, pides datos faltantes y emites tool calls. Nunca confirmes acciones de negocio sin tool_result exitoso.',
  instructions: '1) Comprende la intención.\n2) Recopila datos faltantes.\n3) Emite tool calls client-executed.\n4) Espera resultados.\n5) Escala a humano si es necesario.',
  limits: 'No ejecutar pagos, shell, ni operaciones fuera del backend del cliente.',
  escalation: 'Escalar cuando haya ambigüedad legal, financiera o el usuario lo pida.',
  model_mode: 'automatic',
  memory_enabled: true,
  knowledge_enabled: true,
  tools_note: 'execution_mode=client por defecto',
})

function Field({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label>{label}<input {...props} /></label>
}
function Textarea({ label, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return <label>{label}<textarea {...props} /></label>
}
function Select({ label, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return <label>{label}<select {...props}>{children}</select></label>
}

function ErrorBox({ error }: { error: unknown }) {
  return error ? <div className="error">{error instanceof Error ? error.message : String(error)}</div> : null
}

export function AgentsBuilderPage() {
  const queryClient = useQueryClient()
  const { data: agents = [], error: agentsError } = useQuery({
    queryKey: ['agents'],
    queryFn: () => api<Agent[]>('/agents'),
  })
  const { data: templates = [], error: templatesError } = useQuery({
    queryKey: ['agent-templates'],
    queryFn: () => api<AgentTemplateCard[]>('/agent-templates'),
  })

  // Default to official catalog so users always see the 10 templates first.
  const [tab, setTab] = useState<'agents' | 'templates' | 'wizard'>('templates')
  const [detailSlug, setDetailSlug] = useState<string | null>(null)
  const [wizardStep, setWizardStep] = useState(1)
  const [wizard, setWizard] = useState<WizardState>(emptyWizard)
  const [departmentProfile, setDepartmentProfile] = useState('')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [importJson, setImportJson] = useState('')
  const [message, setMessage] = useState('')

  const { data: templateDetail } = useQuery({
    queryKey: ['agent-template', detailSlug],
    queryFn: () => api<TemplateDetail>(`/agent-templates/${detailSlug}`),
    enabled: Boolean(detailSlug),
  })

  const { data: versions = [] } = useQuery({
    queryKey: ['agent-versions', selectedAgentId],
    queryFn: () => api<Array<{ version: number; label: string; published: boolean }>>(`/agents/${selectedAgentId}/versions`),
    enabled: Boolean(selectedAgentId),
  })

  const createBlank = useMutation({
    mutationFn: () =>
      api<Agent>('/agents', {
        method: 'POST',
        body: JSON.stringify({
          name: wizard.name,
          slug: wizard.slug,
          description: wizard.description,
          system_prompt: `${wizard.system_prompt}\n\nTono: ${wizard.tone}. Personalidad: ${wizard.personality}. Idioma: ${wizard.language}.\nLímites: ${wizard.limits}\nEscalamiento: ${wizard.escalation}`,
          instructions: wizard.instructions,
          memory_enabled: wizard.memory_enabled,
          knowledge_enabled: wizard.knowledge_enabled,
          settings: {
            status: 'draft',
            model_mode: wizard.model_mode,
            language: wizard.language,
            tools_note: wizard.tools_note,
          },
        }),
      }),
    onSuccess: agent => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setMessage(`Agente borrador creado: ${agent.name}`)
      setTab('agents')
      setWizard(emptyWizard())
      setWizardStep(1)
    },
  })

  const install = useMutation({
    mutationFn: (slug: string) =>
      api<Agent>(`/agent-templates/${slug}/install`, {
        method: 'POST',
        body: JSON.stringify({
          name: undefined,
          department_profile: slug === 'department-ai' ? departmentProfile || 'soporte' : undefined,
        }),
      }),
    onSuccess: agent => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setMessage(`Plantilla instalada como borrador: ${agent.name} (${agent.slug})`)
      setTab('agents')
      setDetailSlug(null)
    },
  })

  const publish = useMutation({
    mutationFn: (id: string) =>
      api(`/agents/${id}/publish?label=${encodeURIComponent('Published from Agent Builder')}`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      if (selectedAgentId) queryClient.invalidateQueries({ queryKey: ['agent-versions', selectedAgentId] })
      setMessage('Versión publicada (inmutable).')
    },
  })

  const clone = useMutation({
    mutationFn: (id: string) => api<Agent>(`/agents/${id}/clone`, { method: 'POST' }),
    onSuccess: agent => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setMessage(`Clonado: ${agent.slug}`)
    },
  })

  const restore = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      api<Agent>(`/agents/${id}/versions/${version}/restore`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setMessage('Versión restaurada en el borrador editable.')
    },
  })

  const evaluate = useMutation({
    mutationFn: (id: string) => api(`/agents/${id}/evaluate`, { method: 'POST' }),
    onSuccess: data => setMessage(`Evaluación lista: ${JSON.stringify(data)}`),
  })

  const importManifest = useMutation({
    mutationFn: async () => {
      const parsed = JSON.parse(importJson) as {
        name?: string
        slug?: string
        description?: string
        system_prompt?: string
        instructions?: string
      }
      if (!parsed.name || !parsed.slug || !parsed.system_prompt) {
        throw new Error('Manifiesto incompleto: name, slug y system_prompt son obligatorios')
      }
      return api<Agent>('/agents', {
        method: 'POST',
        body: JSON.stringify({
          name: parsed.name,
          slug: parsed.slug,
          description: parsed.description || '',
          system_prompt: parsed.system_prompt,
          instructions: parsed.instructions || '',
          memory_enabled: true,
          knowledge_enabled: true,
          settings: { status: 'draft', imported: true },
        }),
      })
    },
    onSuccess: agent => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setMessage(`Importado: ${agent.slug}`)
      setImportJson('')
    },
  })

  const categories = useMemo(
    () => Array.from(new Set(templates.map(t => t.category))).sort(),
    [templates],
  )

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <p className="eyebrow">AGENT BUILDER</p>
          <h1>Agentes</h1>
          <p className="muted">
            Crea agentes versionados con instrucciones, modelos, memoria, conocimiento y herramientas independientes.
          </p>
          <p className="muted" style={{ marginTop: 6 }}>
            Create versioned agents with independent prompts, models, memory and tools.
          </p>
        </div>
        <div className="row-actions">
          <button type="button" className="primary compact" onClick={() => { setTab('wizard'); setWizardStep(1); setWizard(emptyWizard()) }}>
            <Plus size={16} /> Nuevo agente
          </button>
          <button type="button" className="secondary compact" onClick={() => setTab('templates')}>
            <Layers size={16} /> Crear desde plantilla
          </button>
          <button type="button" className="secondary compact" onClick={() => setTab('wizard')}>
            <Upload size={16} /> Importar manifiesto
          </button>
        </div>
      </div>

      <div className="create-box" style={{ marginTop: 0, marginBottom: 16 }}>
        <div className="chips">
          <span>10 plantillas oficiales</span>
          <span>execution_mode=client</span>
          <span>versionado inmutable</span>
          <span>Terminal /terminal</span>
        </div>
        <p className="muted" style={{ margin: '10px 0 0' }}>
          Las plantillas globales no se editan. Al pulsar <b>Usar plantilla</b> se crea una <b>copia draft de tu organización</b>.
          Prueba tool calls en <a href="/terminal">Agents Morf Terminal</a>. Integración API en <a href="/docs">/docs</a>.
        </p>
      </div>

      <div className="tabs-row">
        <button type="button" className={tab === 'templates' ? 'tab active' : 'tab'} onClick={() => setTab('templates')}>
          Catálogo ({templates.length || 10})
        </button>
        <button type="button" className={tab === 'agents' ? 'tab active' : 'tab'} onClick={() => setTab('agents')}>
          Mis agentes ({agents.length})
        </button>
        <button type="button" className={tab === 'wizard' ? 'tab active' : 'tab'} onClick={() => setTab('wizard')}>Wizard / Import</button>
      </div>

      {message && <div className="success-banner">{message}</div>}
      <ErrorBox error={agentsError || templatesError || createBlank.error || install.error || publish.error || clone.error || importManifest.error} />
      {templatesError && (
        <div className="warning-banner">
          No se pudo cargar el catálogo desde la API. Si acabas de desplegar, ejecuta en el backend:
          <code> python -m app.cli seed-agent-templates</code>
        </div>
      )}
      {!templatesError && templates.length === 0 && tab === 'templates' && (
        <div className="warning-banner">
          El catálogo está vacío. Ejecuta el seed de plantillas oficiales en el servidor y recarga.
        </div>
      )}

      {tab === 'agents' && (
        <>
          <div className="card-grid">
            {agents.map(agent => (
              <article className="entity-card" key={agent.id}>
                <div className="entity-title">
                  <Bot size={24} />
                  <div>
                    <h3>{agent.name}</h3>
                    <small>{agent.slug} · v{agent.current_version}</small>
                  </div>
                </div>
                <p>{agent.description || 'Sin descripción'}</p>
                <div className="chips">
                  <span>{agent.memory_enabled ? 'Memoria on' : 'Memoria off'}</span>
                  <span>{agent.knowledge_enabled ? 'RAG on' : 'RAG off'}</span>
                  <span>{agent.model || 'router dinámico'}</span>
                  <span>{agent.enabled ? 'enabled' : 'disabled'}</span>
                </div>
                <div className="row-actions" style={{ marginTop: 12 }}>
                  <button type="button" className="secondary compact" onClick={() => setSelectedAgentId(agent.id)}>Versiones</button>
                  <button type="button" className="secondary compact" onClick={() => clone.mutate(agent.id)}><Copy size={14} /> Clonar</button>
                  <button type="button" className="secondary compact" onClick={() => evaluate.mutate(agent.id)}>Evaluar</button>
                  <button type="button" className="primary compact" onClick={() => publish.mutate(agent.id)}>Publicar</button>
                </div>
              </article>
            ))}
            {agents.length === 0 && (
              <div className="empty"><Bot size={40} /><p>Aún no hay agentes. Crea uno o instala una plantilla.</p></div>
            )}
          </div>

          {selectedAgentId && (
            <div className="create-box" style={{ marginTop: 18 }}>
              <h3>Versiones del agente</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Versión</th><th>Label</th><th>Publicada</th><th></th></tr></thead>
                  <tbody>
                    {versions.map(v => (
                      <tr key={v.version}>
                        <td>v{v.version}.0.0</td>
                        <td>{v.label}</td>
                        <td>{v.published ? 'sí' : 'draft'}</td>
                        <td>
                          <button type="button" className="secondary compact" onClick={() => restore.mutate({ id: selectedAgentId, version: v.version })}>
                            Restaurar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'templates' && (
        <>
          <div className="chips" style={{ marginBottom: 14 }}>
            {categories.map(c => <span key={c}>{c}</span>)}
            <span>{templates.length} plantillas oficiales</span>
          </div>
          <div className="card-grid">
            {templates.map(t => (
              <article className="entity-card template-card" key={t.id}>
                <div className="entity-title">
                  <Sparkles size={22} />
                  <div>
                    <h3>{t.name}</h3>
                    <small>{t.slug} · {t.category} · v{t.version}</small>
                  </div>
                </div>
                <p>{t.description}</p>
                <div className="chips">
                  <span>tools: {t.tools_count}</span>
                  <span>{t.memory_enabled ? 'memoria' : 'sin memoria'}</span>
                  <span>{t.knowledge_enabled ? 'RAG' : 'sin RAG'}</span>
                  <span>{t.complexity}</span>
                </div>
                <div className="row-actions" style={{ marginTop: 12 }}>
                  <button type="button" className="secondary compact" onClick={() => setDetailSlug(t.slug)}>
                    <Eye size={14} /> Ver detalles
                  </button>
                  <button type="button" className="primary compact" onClick={() => install.mutate(t.slug)} disabled={install.isPending}>
                    Usar plantilla
                  </button>
                </div>
              </article>
            ))}
          </div>

          {detailSlug && templateDetail && (
            <div className="create-box" style={{ marginTop: 18 }}>
              <div className="panel-head">
                <div>
                  <h3>{templateDetail.name}</h3>
                  <p className="muted">{templateDetail.description}</p>
                </div>
                <button type="button" className="secondary compact" onClick={() => setDetailSlug(null)}>Cerrar</button>
              </div>
              <div className="chips">
                <span>scope={templateDetail.scope || 'global'}</span>
                <span>routing={templateDetail.definition.routing_profile || 'automatic'}</span>
                <span>model={templateDetail.definition.recommended_model_profile || 'balanced'}</span>
              </div>
              {templateDetail.slug === 'department-ai' && (
                <Select label="Department profile" value={departmentProfile} onChange={e => setDepartmentProfile(e.target.value)}>
                  <option value="">— elegir —</option>
                  {(templateDetail.definition.department_profiles || []).map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </Select>
              )}
              <h4>System prompt</h4>
              <pre className="code-block">{templateDetail.definition.system_prompt}</pre>
              <h4>Herramientas (client-executed)</h4>
              <ul className="tool-list">
                {(templateDetail.definition.tools || []).map(tool => (
                  <li key={tool.name}><code>{tool.name}</code> — {tool.description}{tool.requires_approval ? ' · approval' : ''}</li>
                ))}
              </ul>
              <h4>Guardrails</h4>
              <div className="chips">{(templateDetail.definition.guardrails || []).map(g => <span key={g}>{g}</span>)}</div>
              <h4>Evaluación</h4>
              <pre className="code-block">{JSON.stringify(templateDetail.definition.evaluation || {}, null, 2)}</pre>
              <button type="button" className="primary" onClick={() => install.mutate(templateDetail.slug)} disabled={install.isPending}>
                <Check size={16} /> Instalar copia tenant (draft)
              </button>
            </div>
          )}
        </>
      )}

      {tab === 'wizard' && (
        <div className="create-box wizard-box">
          <div className="wizard-steps">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => (
              <button key={n} type="button" className={wizardStep === n ? 'step active' : 'step'} onClick={() => setWizardStep(n)}>
                {n}
              </button>
            ))}
          </div>

          {wizardStep === 1 && (
            <div className="form-grid">
              <Field label="Nombre" value={wizard.name} onChange={e => setWizard({
                ...wizard,
                name: e.target.value,
                slug: wizard.slug || e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
              })} required />
              <Field label="Slug" value={wizard.slug} onChange={e => setWizard({ ...wizard, slug: e.target.value })} required />
              <Field label="Descripción" value={wizard.description} onChange={e => setWizard({ ...wizard, description: e.target.value })} />
              <Field label="Idioma" value={wizard.language} onChange={e => setWizard({ ...wizard, language: e.target.value })} />
              <Field label="Tono" value={wizard.tone} onChange={e => setWizard({ ...wizard, tone: e.target.value })} />
              <Field label="Personalidad" value={wizard.personality} onChange={e => setWizard({ ...wizard, personality: e.target.value })} />
            </div>
          )}
          {wizardStep === 2 && (
            <div className="form-grid">
              <Textarea label="System prompt" value={wizard.system_prompt} onChange={e => setWizard({ ...wizard, system_prompt: e.target.value })} />
              <Textarea label="Instrucciones" value={wizard.instructions} onChange={e => setWizard({ ...wizard, instructions: e.target.value })} />
              <Textarea label="Límites" value={wizard.limits} onChange={e => setWizard({ ...wizard, limits: e.target.value })} />
              <Textarea label="Escalamiento humano" value={wizard.escalation} onChange={e => setWizard({ ...wizard, escalation: e.target.value })} />
            </div>
          )}
          {wizardStep === 3 && (
            <div className="form-grid">
              <Select label="Modo de modelo" value={wizard.model_mode} onChange={e => setWizard({ ...wizard, model_mode: e.target.value })}>
                <option value="automatic">Automático</option>
                <option value="fast">Rápido</option>
                <option value="economy">Económico</option>
                <option value="private">Privado</option>
                <option value="quality">Máxima calidad</option>
              </Select>
              <p className="muted">El enrutamiento real lo decide el hybrid router del backend (capacidad, no proveedor fijo). Ollama no se usa para chat productivo.</p>
            </div>
          )}
          {wizardStep === 4 && (
            <div className="form-grid">
              <label className="check-row"><input type="checkbox" checked={wizard.memory_enabled} onChange={e => setWizard({ ...wizard, memory_enabled: e.target.checked })} /> Memoria activada</label>
              <p className="muted">Scopes y retención se gestionan en backend; el cliente no administra memoria de plataforma.</p>
            </div>
          )}
          {wizardStep === 5 && (
            <div className="form-grid">
              <label className="check-row"><input type="checkbox" checked={wizard.knowledge_enabled} onChange={e => setWizard({ ...wizard, knowledge_enabled: e.target.checked })} /> Knowledge / RAG</label>
              <p className="muted">Vincula bases de conocimiento después de crear el agente desde la sección Knowledge.</p>
            </div>
          )}
          {wizardStep === 6 && (
            <div className="form-grid">
              <Textarea label="Notas de herramientas" value={wizard.tools_note} onChange={e => setWizard({ ...wizard, tools_note: e.target.value })} />
              <p className="muted">execution_mode=client por defecto. Server tools opcionales y deshabilitados salvo política explícita.</p>
            </div>
          )}
          {wizardStep === 7 && (
            <div>
              <p className="muted">Tras crear el agente, usa ejemplos de la plantilla o Training (platform) para datasets de evaluación conductual. No es fine-tuning de pesos.</p>
            </div>
          )}
          {wizardStep === 8 && (
            <div>
              <p className="muted">Prueba el agente en <strong>Agents Morf Terminal</strong> (/terminal): tool calls, simulador de tool_result, memoria y RAG.</p>
            </div>
          )}
          {wizardStep === 9 && (
            <div>
              <p>Revisa y crea el borrador. Luego publica una versión inmutable desde Mis agentes.</p>
              <pre className="code-block">{JSON.stringify(wizard, null, 2)}</pre>
            </div>
          )}

          <div className="row-actions" style={{ marginTop: 16 }}>
            <button type="button" className="secondary compact" disabled={wizardStep <= 1} onClick={() => setWizardStep(s => Math.max(1, s - 1))}>Anterior</button>
            <button type="button" className="secondary compact" disabled={wizardStep >= 9} onClick={() => setWizardStep(s => Math.min(9, s + 1))}>Siguiente</button>
            {wizardStep === 9 && (
              <button type="button" className="primary" onClick={() => createBlank.mutate()} disabled={createBlank.isPending || !wizard.name || !wizard.slug}>
                <Save size={16} /> Crear borrador
              </button>
            )}
          </div>

          <hr style={{ margin: '24px 0', borderColor: 'var(--border)' }} />
          <h3>Importar manifiesto JSON</h3>
          <Textarea label="JSON" value={importJson} onChange={e => setImportJson(e.target.value)} placeholder='{"name":"...","slug":"...","system_prompt":"..."}' />
          <button type="button" className="secondary" onClick={() => importManifest.mutate()} disabled={importManifest.isPending}>
            <Upload size={16} /> Importar como draft
          </button>
        </div>
      )}
    </section>
  )
}
