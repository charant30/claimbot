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
    calculation_result: Record<string, any> | null
    messages: Array<{ role: string; content: string }>
    created_at: string
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
                const data = await handoffApi.getCase(caseId!)
                setCaseData(data)
            } catch (error) {
                console.error('Failed to fetch case:', error)
                // Mock data
                setCaseData({
                    case_id: caseId!,
                    thread_id: 'thread-001',
                    status: 'pending',
                    priority: 'high',
                    reason: 'High-value claim requires review',
                    customer_name: 'Alice Johnson',
                    customer_email: 'alice@example.com',
                    claim_type: 'auto',
                    policy_number: 'AUT-2024-001234',
                    collected_fields: {
                        incident_date: '2024-01-15',
                        incident_location: '123 Main St, New York, NY',
                        incident_description: 'Rear-ended at traffic light. Damage to rear bumper and trunk.',
                        estimated_damage: 8500,
                        police_report_number: 'PR-2024-5678',
                    },
                    calculation_result: {
                        payout_amount: 8000,
                        deductible_applied: 500,
                        is_total_loss: false,
                    },
                    messages: [
                        { role: 'user', content: "I need to file a claim for a car accident." },
                        { role: 'assistant', content: "I'm sorry to hear about your accident. I'll help you file a claim. Can you tell me when and where the incident occurred?" },
                        { role: 'user', content: "It happened yesterday at 123 Main St. I was rear-ended at a traffic light." },
                    ],
                    created_at: new Date(Date.now() - 300000).toISOString(),
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
                        <h2>Extracted Data</h2>
                        <div className="extracted-fields">
                            {Object.entries(caseData.collected_fields).map(([key, value]) => (
                                <div key={key} className="field-item">
                                    <span className="field-label">{key.replace(/_/g, ' ')}</span>
                                    <span className="field-value">{String(value)}</span>
                                </div>
                            ))}
                        </div>
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
