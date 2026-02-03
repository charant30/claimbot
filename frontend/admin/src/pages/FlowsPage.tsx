import { useState, useEffect } from 'react'
import { adminApi } from '../services/api'
import './FlowsPage.css'

// Types
interface Intent {
    intent_id?: string
    name: string
    display_name: string
    description?: string
    applicable_products?: string[]
    trigger_phrases?: string[]
    required_fields?: string[]
    flow_config?: Record<string, unknown>
    icon?: string
    is_active?: boolean
    priority?: number
}

interface FlowRule {
    rule_id?: string
    name: string
    description?: string
    conditions: Record<string, unknown>
    action: Record<string, unknown>
    is_active?: boolean
    priority?: number
}

interface DocumentFlow {
    config_id?: string
    product_line: string
    incident_type?: string
    document_sequence: string[]
    conditional_rules?: Record<string, unknown>
    field_requirements?: Record<string, string[]>
    is_active?: boolean
    is_default?: boolean
}

interface FlowSettings {
    confidence_threshold: number
    auto_approval_limit: number
}

type TabType = 'intents' | 'document-flows' | 'flow-rules'

const PRODUCT_LINES = ['auto', 'home', 'medical']
const DOCUMENT_TYPES = [
    'police_report',
    'incident_photos',
    'repair_estimate',
    'invoice',
    'eob',
    'fire_department_report',
    'medical_records',
]

function FlowsPage() {
    const [activeTab, setActiveTab] = useState<TabType>('intents')
    const [intents, setIntents] = useState<Intent[]>([])
    const [flowRules, setFlowRules] = useState<FlowRule[]>([])
    const [documentFlows, setDocumentFlows] = useState<DocumentFlow[]>([])
    const [flowSettings, setFlowSettings] = useState<FlowSettings>({
        confidence_threshold: 0.7,
        auto_approval_limit: 5000,
    })
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Modal state
    const [showModal, setShowModal] = useState(false)
    const [modalMode, setModalMode] = useState<'create' | 'edit'>('create')
    const [editingItem, setEditingItem] = useState<Intent | FlowRule | DocumentFlow | null>(null)

    useEffect(() => {
        fetchData()
    }, [])

    const fetchData = async () => {
        setLoading(true)
        setError(null)
        try {
            const [intentsData, flowsData, docFlowsData] = await Promise.all([
                adminApi.getIntents(),
                adminApi.getFlows(),
                adminApi.getDocumentFlows(),
            ])
            setIntents(intentsData.intents || [])
            setFlowRules(flowsData.rules || [])
            setFlowSettings(flowsData.settings || { confidence_threshold: 0.7, auto_approval_limit: 5000 })
            setDocumentFlows(docFlowsData.document_flows || [])
        } catch (err) {
            console.error('Failed to fetch flows:', err)
            setError('Failed to load configuration data')
        } finally {
            setLoading(false)
        }
    }

    const handleSaveSettings = async () => {
        setSaving(true)
        try {
            await adminApi.updateFlowSettings(flowSettings)
        } catch (err) {
            console.error('Failed to save settings:', err)
            setError('Failed to save settings')
        } finally {
            setSaving(false)
        }
    }

    const openCreateModal = () => {
        setModalMode('create')
        setEditingItem(null)
        setShowModal(true)
    }

    const openEditModal = (item: Intent | FlowRule | DocumentFlow) => {
        setModalMode('edit')
        setEditingItem(item)
        setShowModal(true)
    }

    const handleDelete = async (item: Intent | FlowRule | DocumentFlow) => {
        if (!confirm('Are you sure you want to delete this item?')) return

        try {
            if (activeTab === 'intents' && 'intent_id' in item && item.intent_id) {
                await adminApi.deleteIntent(item.intent_id)
            } else if (activeTab === 'flow-rules' && 'rule_id' in item && item.rule_id) {
                await adminApi.deleteFlowRule(item.rule_id)
            } else if (activeTab === 'document-flows' && 'config_id' in item && item.config_id) {
                await adminApi.deleteDocumentFlow(item.config_id)
            }
            await fetchData()
        } catch (err) {
            console.error('Failed to delete:', err)
            setError('Failed to delete item')
        }
    }

    if (loading) {
        return <div className="loading">Loading configuration...</div>
    }

    return (
        <div className="flows-page">
            <div className="page-header">
                <h1>Flows & Intents</h1>
                <p>Configure chat intents, document flows, and routing rules</p>
            </div>

            {error && (
                <div className="error-banner">
                    {error}
                    <button onClick={() => setError(null)}>Dismiss</button>
                </div>
            )}

            {/* Tabs */}
            <div className="tabs">
                <button
                    className={`tab ${activeTab === 'intents' ? 'active' : ''}`}
                    onClick={() => setActiveTab('intents')}
                >
                    Intents ({intents.length})
                </button>
                <button
                    className={`tab ${activeTab === 'document-flows' ? 'active' : ''}`}
                    onClick={() => setActiveTab('document-flows')}
                >
                    Document Flows ({documentFlows.length})
                </button>
                <button
                    className={`tab ${activeTab === 'flow-rules' ? 'active' : ''}`}
                    onClick={() => setActiveTab('flow-rules')}
                >
                    Flow Rules ({flowRules.length})
                </button>
            </div>

            {/* Tab Content */}
            <div className="tab-content">
                {activeTab === 'intents' && (
                    <IntentsTab
                        intents={intents}
                        onAdd={openCreateModal}
                        onEdit={openEditModal}
                        onDelete={handleDelete}
                    />
                )}

                {activeTab === 'document-flows' && (
                    <DocumentFlowsTab
                        flows={documentFlows}
                        onAdd={openCreateModal}
                        onEdit={openEditModal}
                        onDelete={handleDelete}
                    />
                )}

                {activeTab === 'flow-rules' && (
                    <FlowRulesTab
                        rules={flowRules}
                        settings={flowSettings}
                        onSettingsChange={setFlowSettings}
                        onSaveSettings={handleSaveSettings}
                        saving={saving}
                        onAdd={openCreateModal}
                        onEdit={openEditModal}
                        onDelete={handleDelete}
                    />
                )}
            </div>

            {/* Modal */}
            {showModal && (
                <Modal
                    type={activeTab}
                    mode={modalMode}
                    item={editingItem}
                    onClose={() => setShowModal(false)}
                    onSave={async (data) => {
                        try {
                            if (activeTab === 'intents') {
                                if (modalMode === 'create') {
                                    await adminApi.createIntent(data as Intent)
                                } else if (editingItem && 'intent_id' in editingItem && editingItem.intent_id) {
                                    await adminApi.updateIntent(editingItem.intent_id, data)
                                }
                            } else if (activeTab === 'document-flows') {
                                if (modalMode === 'create') {
                                    await adminApi.createDocumentFlow(data as DocumentFlow)
                                } else if (editingItem && 'config_id' in editingItem && editingItem.config_id) {
                                    await adminApi.updateDocumentFlow(editingItem.config_id, data)
                                }
                            } else if (activeTab === 'flow-rules') {
                                if (modalMode === 'create') {
                                    await adminApi.createFlowRule(data as FlowRule)
                                } else if (editingItem && 'rule_id' in editingItem && editingItem.rule_id) {
                                    await adminApi.updateFlowRule(editingItem.rule_id, data)
                                }
                            }
                            setShowModal(false)
                            await fetchData()
                        } catch (err) {
                            console.error('Failed to save:', err)
                            setError('Failed to save item')
                        }
                    }}
                />
            )}
        </div>
    )
}

// Intents Tab Component
function IntentsTab({
    intents,
    onAdd,
    onEdit,
    onDelete,
}: {
    intents: Intent[]
    onAdd: () => void
    onEdit: (item: Intent) => void
    onDelete: (item: Intent) => void
}) {
    return (
        <section className="section">
            <div className="section-header">
                <h2>Configured Intents</h2>
                <button className="btn-primary" onClick={onAdd}>
                    + Add Intent
                </button>
            </div>
            <div className="intents-grid">
                {intents.map((intent, index) => (
                    <div key={intent.intent_id || index} className="intent-card">
                        <div className="card-header">
                            <span className="icon">{intent.icon || '...'}</span>
                            <h3>{intent.display_name || intent.name}</h3>
                            <span className={`status-badge ${intent.is_active !== false ? 'active' : 'inactive'}`}>
                                {intent.is_active !== false ? 'Active' : 'Inactive'}
                            </span>
                        </div>
                        <p className="intent-name">ID: {intent.name}</p>
                        <p className="description">{intent.description || 'No description'}</p>
                        {intent.applicable_products && intent.applicable_products.length > 0 && (
                            <div className="products">
                                {intent.applicable_products.map((p) => (
                                    <span key={p} className="product-tag">{p}</span>
                                ))}
                            </div>
                        )}
                        <div className="card-actions">
                            <button onClick={() => onEdit(intent)}>Edit</button>
                            <button className="btn-danger" onClick={() => onDelete(intent)}>Delete</button>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    )
}

// Document Flows Tab Component
function DocumentFlowsTab({
    flows,
    onAdd,
    onEdit,
    onDelete,
}: {
    flows: DocumentFlow[]
    onAdd: () => void
    onEdit: (item: DocumentFlow) => void
    onDelete: (item: DocumentFlow) => void
}) {
    return (
        <section className="section">
            <div className="section-header">
                <h2>Document Flow Configurations</h2>
                <button className="btn-primary" onClick={onAdd}>
                    + Add Document Flow
                </button>
            </div>
            <div className="flows-list">
                {flows.map((flow, index) => (
                    <div key={flow.config_id || index} className="flow-card">
                        <div className="flow-header">
                            <h3>
                                {flow.product_line.toUpperCase()}
                                {flow.incident_type && ` / ${flow.incident_type}`}
                            </h3>
                            {flow.is_default && <span className="default-badge">Default</span>}
                        </div>
                        <div className="document-sequence">
                            <strong>Document Sequence:</strong>
                            <div className="sequence-flow">
                                {flow.document_sequence.map((doc, i) => (
                                    <span key={i} className="doc-step">
                                        {i > 0 && <span className="arrow">-&gt;</span>}
                                        {doc.replace('_', ' ')}
                                    </span>
                                ))}
                            </div>
                        </div>
                        {!flow.is_default && (
                            <div className="card-actions">
                                <button onClick={() => onEdit(flow)}>Edit</button>
                                <button className="btn-danger" onClick={() => onDelete(flow)}>Delete</button>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </section>
    )
}

// Flow Rules Tab Component
function FlowRulesTab({
    rules,
    settings,
    onSettingsChange,
    onSaveSettings,
    saving,
    onAdd,
    onEdit,
    onDelete,
}: {
    rules: FlowRule[]
    settings: FlowSettings
    onSettingsChange: (settings: FlowSettings) => void
    onSaveSettings: () => void
    saving: boolean
    onAdd: () => void
    onEdit: (item: FlowRule) => void
    onDelete: (item: FlowRule) => void
}) {
    return (
        <section className="section">
            {/* General Settings */}
            <div className="settings-card">
                <h3>General Flow Settings</h3>
                <div className="settings-form">
                    <label>
                        Confidence Threshold
                        <input
                            type="number"
                            step="0.1"
                            min="0"
                            max="1"
                            value={settings.confidence_threshold}
                            onChange={(e) => onSettingsChange({
                                ...settings,
                                confidence_threshold: parseFloat(e.target.value),
                            })}
                        />
                        <span className="hint">Claims below this confidence will be escalated</span>
                    </label>
                    <label>
                        Auto-Approval Limit ($)
                        <input
                            type="number"
                            step="100"
                            min="0"
                            value={settings.auto_approval_limit}
                            onChange={(e) => onSettingsChange({
                                ...settings,
                                auto_approval_limit: parseInt(e.target.value),
                            })}
                        />
                        <span className="hint">Claims above this amount require manual review</span>
                    </label>
                    <button
                        className="btn-primary"
                        onClick={onSaveSettings}
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : 'Save Settings'}
                    </button>
                </div>
            </div>

            {/* Rules List */}
            <div className="section-header">
                <h3>Routing Rules</h3>
                <button className="btn-primary" onClick={onAdd}>
                    + Add Rule
                </button>
            </div>
            <div className="rules-list">
                {rules.length === 0 ? (
                    <p className="empty-state">No custom routing rules configured. Default rules will apply.</p>
                ) : (
                    rules.map((rule, index) => (
                        <div key={rule.rule_id || index} className="rule-card">
                            <div className="rule-header">
                                <h4>{rule.name}</h4>
                                <span className="priority">Priority: {rule.priority || 0}</span>
                            </div>
                            <p className="description">{rule.description || 'No description'}</p>
                            <div className="rule-details">
                                <div className="conditions">
                                    <strong>Conditions:</strong>
                                    <pre>{JSON.stringify(rule.conditions, null, 2)}</pre>
                                </div>
                                <div className="actions">
                                    <strong>Action:</strong>
                                    <pre>{JSON.stringify(rule.action, null, 2)}</pre>
                                </div>
                            </div>
                            <div className="card-actions">
                                <button onClick={() => onEdit(rule)}>Edit</button>
                                <button className="btn-danger" onClick={() => onDelete(rule)}>Delete</button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </section>
    )
}

// Modal Component
function Modal({
    type,
    mode,
    item,
    onClose,
    onSave,
}: {
    type: TabType
    mode: 'create' | 'edit'
    item: Intent | FlowRule | DocumentFlow | null
    onClose: () => void
    onSave: (data: Record<string, unknown>) => void
}) {
    const [formData, setFormData] = useState<Record<string, unknown>>(item || {})

    useEffect(() => {
        if (item) {
            setFormData(item)
        } else {
            // Default values for new items
            if (type === 'intents') {
                setFormData({ name: '', display_name: '', applicable_products: [], is_active: true })
            } else if (type === 'document-flows') {
                setFormData({ product_line: 'auto', document_sequence: [] })
            } else {
                setFormData({ name: '', conditions: {}, action: {}, priority: 0 })
            }
        }
    }, [item, type])

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onSave(formData)
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>{mode === 'create' ? 'Create' : 'Edit'} {type.replace('-', ' ')}</h2>
                    <button className="close-btn" onClick={onClose}>x</button>
                </div>
                <form onSubmit={handleSubmit}>
                    {type === 'intents' && (
                        <IntentForm formData={formData} setFormData={setFormData} />
                    )}
                    {type === 'document-flows' && (
                        <DocumentFlowForm formData={formData} setFormData={setFormData} />
                    )}
                    {type === 'flow-rules' && (
                        <FlowRuleForm formData={formData} setFormData={setFormData} />
                    )}
                    <div className="modal-actions">
                        <button type="button" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
    )
}

// Form Components
function IntentForm({
    formData,
    setFormData,
}: {
    formData: Record<string, unknown>
    setFormData: (data: Record<string, unknown>) => void
}) {
    return (
        <div className="form-fields">
            <label>
                Name (ID)
                <input
                    type="text"
                    value={(formData.name as string) || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    pattern="[a-z_]+"
                    placeholder="e.g., file_claim"
                />
            </label>
            <label>
                Display Name
                <input
                    type="text"
                    value={(formData.display_name as string) || ''}
                    onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                    required
                    placeholder="e.g., File a New Claim"
                />
            </label>
            <label>
                Icon (emoji)
                <input
                    type="text"
                    value={(formData.icon as string) || ''}
                    onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                    placeholder="e.g., 📝"
                />
            </label>
            <label>
                Description
                <textarea
                    value={(formData.description as string) || ''}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Describe what this intent does..."
                />
            </label>
            <label>
                Applicable Products
                <div className="checkbox-group">
                    {PRODUCT_LINES.map((pl) => (
                        <label key={pl} className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={((formData.applicable_products as string[]) || []).includes(pl)}
                                onChange={(e) => {
                                    const current = (formData.applicable_products as string[]) || []
                                    const updated = e.target.checked
                                        ? [...current, pl]
                                        : current.filter((p) => p !== pl)
                                    setFormData({ ...formData, applicable_products: updated })
                                }}
                            />
                            {pl}
                        </label>
                    ))}
                </div>
            </label>
            <label className="checkbox-label">
                <input
                    type="checkbox"
                    checked={(formData.is_active as boolean) !== false}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                Active
            </label>
        </div>
    )
}

function DocumentFlowForm({
    formData,
    setFormData,
}: {
    formData: Record<string, unknown>
    setFormData: (data: Record<string, unknown>) => void
}) {
    const [newDoc, setNewDoc] = useState('')

    const addDocument = () => {
        if (newDoc) {
            const current = (formData.document_sequence as string[]) || []
            setFormData({ ...formData, document_sequence: [...current, newDoc] })
            setNewDoc('')
        }
    }

    const removeDocument = (index: number) => {
        const current = (formData.document_sequence as string[]) || []
        setFormData({ ...formData, document_sequence: current.filter((_, i) => i !== index) })
    }

    return (
        <div className="form-fields">
            <label>
                Product Line
                <select
                    value={(formData.product_line as string) || 'auto'}
                    onChange={(e) => setFormData({ ...formData, product_line: e.target.value })}
                    required
                >
                    {PRODUCT_LINES.map((pl) => (
                        <option key={pl} value={pl}>{pl}</option>
                    ))}
                </select>
            </label>
            <label>
                Incident Type (optional)
                <input
                    type="text"
                    value={(formData.incident_type as string) || ''}
                    onChange={(e) => setFormData({ ...formData, incident_type: e.target.value || null })}
                    placeholder="e.g., collision, theft, fire"
                />
            </label>
            <label>
                Document Sequence
                <div className="sequence-builder">
                    <div className="current-sequence">
                        {((formData.document_sequence as string[]) || []).map((doc, i) => (
                            <span key={i} className="sequence-item">
                                {doc}
                                <button type="button" onClick={() => removeDocument(i)}>x</button>
                            </span>
                        ))}
                    </div>
                    <div className="add-doc">
                        <select value={newDoc} onChange={(e) => setNewDoc(e.target.value)}>
                            <option value="">Select document type...</option>
                            {DOCUMENT_TYPES.map((dt) => (
                                <option key={dt} value={dt}>{dt.replace('_', ' ')}</option>
                            ))}
                        </select>
                        <button type="button" onClick={addDocument}>Add</button>
                    </div>
                </div>
            </label>
        </div>
    )
}

function FlowRuleForm({
    formData,
    setFormData,
}: {
    formData: Record<string, unknown>
    setFormData: (data: Record<string, unknown>) => void
}) {
    return (
        <div className="form-fields">
            <label>
                Rule Name
                <input
                    type="text"
                    value={(formData.name as string) || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    placeholder="e.g., High Value Auto Claims"
                />
            </label>
            <label>
                Description
                <textarea
                    value={(formData.description as string) || ''}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Describe when this rule should trigger..."
                />
            </label>
            <label>
                Priority
                <input
                    type="number"
                    value={(formData.priority as number) || 0}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                />
                <span className="hint">Higher priority rules are evaluated first</span>
            </label>
            <label>
                Conditions (JSON)
                <textarea
                    value={JSON.stringify(formData.conditions || {}, null, 2)}
                    onChange={(e) => {
                        try {
                            setFormData({ ...formData, conditions: JSON.parse(e.target.value) })
                        } catch {
                            // Invalid JSON, ignore
                        }
                    }}
                    placeholder='{"product_line": "auto", "claim_amount_gt": 5000}'
                    className="json-input"
                />
            </label>
            <label>
                Action (JSON)
                <textarea
                    value={JSON.stringify(formData.action || {}, null, 2)}
                    onChange={(e) => {
                        try {
                            setFormData({ ...formData, action: JSON.parse(e.target.value) })
                        } catch {
                            // Invalid JSON, ignore
                        }
                    }}
                    placeholder='{"escalate": true, "reason": "High-value claim"}'
                    className="json-input"
                />
            </label>
        </div>
    )
}

export default FlowsPage
