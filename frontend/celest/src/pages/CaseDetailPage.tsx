import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { handoffApi } from '../services/api'
import './CaseDetailPage.css'

interface CaseDetail {
    case_id: string
    thread_id: string
    status: string
    priority: string
    reason: string
    customer_name: string
    customer_email: string
    claim_type: string
    policy_number: string
    collected_fields: Record<string, any>
    intent?: string
    product_line?: string
    calculation_result: Record<string, any> | null
    messages: Array<{ role: string; content: string }>
    created_at: string
}

function formatIntent(intent: string): string {
    const labels: Record<string, string> = {
        billing_inquiry: 'Billing inquiry',
        coverage_question: 'Coverage question',
        check_status: 'Claim status',
        human_request: 'Speak to agent',
        general_inquiry: 'General inquiry',
    }
    return labels[intent] || intent.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function CaseDetailPage() {
    const { caseId } = useParams()
    const navigate = useNavigate()
    const [caseData, setCaseData] = useState<CaseDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [actionLoading, setActionLoading] = useState(false)
    const [notes, setNotes] = useState('')
    const [showDenyModal, setShowDenyModal] = useState(false)
    const [denyReason, setDenyReason] = useState('')

    useEffect(() => {
        const fetchCase = async () => {
            try {
                // Fetch case details and messages in parallel
                const [caseRes, messagesRes] = await Promise.all([
                    handoffApi.getCase(caseId!),
                    handoffApi.getMessages(caseId!)
                ])

                const packet = caseRes.case_packet || {}
                const collected = packet.collected_fields || {}
                const calculation = packet.calculation_result || null

                // Map to CaseDetail interface
                const mappedData: CaseDetail = {
                    case_id: caseRes.case_id,
                    thread_id: caseRes.thread_id,
                    status: caseRes.status,
                    priority: String(caseRes.priority),
                    reason: packet.escalation_reason || packet.reason || 'Manual Escalation',
                    customer_name: packet.first_name ? `${packet.first_name} ${packet.last_name || ''}` : 'Unknown Customer',
                    customer_email: packet.email || 'No Email',
                    claim_type: packet.incident_type || 'General',
                    policy_number: packet.policy_number || collected.policy_number || 'N/A',
                    collected_fields: collected,
                    intent: packet.intent,
                    product_line: packet.product_line,
                    calculation_result: calculation,
                    messages: Array.isArray(messagesRes) ? messagesRes : [],
                    created_at: caseRes.created_at
                }

                setCaseData(mappedData)
            } catch (error) {
                console.error('Failed to fetch case:', error)
                // Fallback to mock data if fetch fails
                setCaseData({
                    case_id: caseId!,
                    thread_id: 'thread-001',
                    status: 'pending',
                    priority: 'high',
                    reason: 'Error loading case details',
                    customer_name: 'Unknown',
                    customer_email: 'unknown@example.com',
                    claim_type: 'auto',
                    policy_number: 'N/A',
                    collected_fields: {},
                    intent: undefined,
                    product_line: undefined,
                    calculation_result: null,
                    messages: [],
                    created_at: new Date().toISOString(),
                })
            } finally {
                setLoading(false)
            }
        }
        fetchCase()
    }, [caseId])

    const handleApprove = async () => {
        setActionLoading(true)
        try {
            await handoffApi.approveCase(caseId!, notes)
            navigate('/')
        } catch (error) {
            console.error('Failed to approve:', error)
        } finally {
            setActionLoading(false)
        }
    }

    const handleDeny = async () => {
        if (!denyReason) return
        setActionLoading(true)
        try {
            await handoffApi.denyCase(caseId!, denyReason)
            navigate('/')
        } catch (error) {
            console.error('Failed to deny:', error)
        } finally {
            setActionLoading(false)
            setShowDenyModal(false)
        }
    }

    const handleTakeover = async () => {
        setActionLoading(true)
        try {
            await handoffApi.takeover(caseId!)
            navigate(`/live-chat/${caseId}`)
        } catch (error) {
            console.error('Failed to takeover:', error)
        } finally {
            setActionLoading(false)
        }
    }

    if (loading || !caseData) {
        return <div className="loading">Loading case...</div>
    }

    return (
        <div className="case-detail-page">
            <div className="page-header">
                <Link to="/" className="back-link">← Back to Queue</Link>
                <h1>Case #{caseId?.slice(0, 8)}</h1>
            </div>

            <div className="case-layout">
                {/* Left: Case Info */}
                <div className="case-info">
                    <section className="info-section">
                        <h2>Customer</h2>
                        <div className="info-grid">
                            <div className="info-item">
                                <span className="label">Name</span>
                                <span className="value">{caseData.customer_name}</span>
                            </div>
                            <div className="info-item">
                                <span className="label">Email</span>
                                <span className="value">{caseData.customer_email}</span>
                            </div>
                            <div className="info-item">
                                <span className="label">Policy</span>
                                <span className="value">{caseData.policy_number}</span>
                            </div>
                        </div>
                    </section>

                    <section className="info-section">
                        {Object.keys(caseData.collected_fields).length > 0 ? (
                            <>
                                <h2>Extracted Data</h2>
                                <p className="section-desc">Claim form data collected during intake (FNOL).</p>
                                <div className="extracted-fields">
                                    {Object.entries(caseData.collected_fields).map(([key, value]) => (
                                        <div key={key} className="field-item">
                                            <span className="field-label">{key.replace(/_/g, ' ')}</span>
                                            <span className="field-value">{String(value)}</span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <>
                                <h2>Case Context</h2>
                                <p className="section-desc">Summary for chat or inquiry escalations.</p>
                                <div className="info-grid">
                                    {caseData.intent && (
                                        <div className="info-item">
                                            <span className="label">Intent</span>
                                            <span className="value">{formatIntent(caseData.intent)}</span>
                                        </div>
                                    )}
                                    {caseData.product_line && (
                                        <div className="info-item">
                                            <span className="label">Product</span>
                                            <span className="value">{String(caseData.product_line).charAt(0).toUpperCase() + String(caseData.product_line).slice(1)}</span>
                                        </div>
                                    )}
                                    <div className="info-item">
                                        <span className="label">Reason</span>
                                        <span className="value">{caseData.reason}</span>
                                    </div>
                                    {!caseData.intent && !caseData.product_line && (
                                        <div className="info-item">
                                            <span className="value muted">No additional context (see transcript).</span>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
                    </section>

                    {caseData.calculation_result && (
                        <section className="info-section">
                            <h2>Calculation Result</h2>
                            <div className="calculation-box">
                                <div className="calc-item">
                                    <span className="calc-label">Estimated Payout</span>
                                    <span className="calc-value">${caseData.calculation_result.payout_amount?.toLocaleString()}</span>
                                </div>
                                <div className="calc-item">
                                    <span className="calc-label">Deductible Applied</span>
                                    <span className="calc-value">${caseData.calculation_result.deductible_applied?.toLocaleString()}</span>
                                </div>
                            </div>
                        </section>
                    )}
                </div>

                {/* Right: Transcript + Actions */}
                <div className="case-actions">
                    <section className="transcript-section">
                        <h2>Conversation Transcript</h2>
                        <div className="transcript">
                            {caseData.messages.map((msg, idx) => (
                                <div key={idx} className={`message ${msg.role}`}>
                                    <span className="role">{msg.role === 'user' ? '👤 Customer' : '🤖 AI'}</span>
                                    <p>{msg.content}</p>
                                </div>
                            ))}
                        </div>
                    </section>

                    <section className="actions-section">
                        <h2>Actions</h2>
                        <div className="notes-input">
                            <label>Notes (optional)</label>
                            <textarea
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Add any notes before taking action..."
                                rows={3}
                            />
                        </div>
                        <div className="action-buttons">
                            <button
                                className="btn btn-success"
                                onClick={handleApprove}
                                disabled={actionLoading}
                            >
                                ✓ Approve Claim
                            </button>
                            <button
                                className="btn btn-danger"
                                onClick={() => setShowDenyModal(true)}
                                disabled={actionLoading}
                            >
                                ✗ Deny Claim
                            </button>
                            <button
                                className="btn btn-primary"
                                onClick={handleTakeover}
                                disabled={actionLoading}
                            >
                                💬 Take Over Chat
                            </button>
                        </div>
                    </section>
                </div>
            </div>

            {/* Deny Modal */}
            {showDenyModal && (
                <div className="modal-overlay" onClick={() => setShowDenyModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <h3>Deny Claim</h3>
                        <p>Please provide a reason for denial:</p>
                        <textarea
                            value={denyReason}
                            onChange={(e) => setDenyReason(e.target.value)}
                            placeholder="Reason for denial..."
                            rows={4}
                        />
                        <div className="modal-actions">
                            <button className="btn btn-secondary" onClick={() => setShowDenyModal(false)}>
                                Cancel
                            </button>
                            <button
                                className="btn btn-danger"
                                onClick={handleDeny}
                                disabled={!denyReason || actionLoading}
                            >
                                Confirm Denial
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default CaseDetailPage
