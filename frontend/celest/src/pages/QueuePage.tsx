import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { handoffApi } from '../services/api'
import './QueuePage.css'

interface EscalatedCase {
    case_id: string
    thread_id: string
    status: string
    priority: string
    reason: string
    customer_name: string
    customer_email: string
    claim_type: string
    created_at: string
    sla_deadline: string
}

function QueuePage() {
    const [cases, setCases] = useState<EscalatedCase[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchQueue = async () => {
            try {
                const data = await handoffApi.getQueue()
                setCases(data)
            } catch (error) {
                console.error('Failed to fetch queue:', error)
                // Mock data for demo
                setCases([
                    {
                        case_id: 'case-001',
                        thread_id: 'thread-001',
                        status: 'pending',
                        priority: 'high',
                        reason: 'High-value claim requires review',
                        customer_name: 'Alice Johnson',
                        customer_email: 'alice@example.com',
                        claim_type: 'auto',
                        created_at: new Date(Date.now() - 300000).toISOString(),
                        sla_deadline: new Date(Date.now() + 900000).toISOString(),
                    },
                    {
                        case_id: 'case-002',
                        thread_id: 'thread-002',
                        status: 'pending',
                        priority: 'medium',
                        reason: 'User requested human agent',
                        customer_name: 'Bob Smith',
                        customer_email: 'bob@example.com',
                        claim_type: 'medical',
                        created_at: new Date(Date.now() - 600000).toISOString(),
                        sla_deadline: new Date(Date.now() + 1200000).toISOString(),
                    },
                    {
                        case_id: 'case-003',
                        thread_id: 'thread-003',
                        status: 'pending',
                        priority: 'low',
                        reason: 'Low confidence in AI response',
                        customer_name: 'Carol Williams',
                        customer_email: 'carol@example.com',
                        claim_type: 'home',
                        created_at: new Date(Date.now() - 1200000).toISOString(),
                        sla_deadline: new Date(Date.now() + 1800000).toISOString(),
                    },
                ])
            } finally {
                setLoading(false)
            }
        }
        fetchQueue()
    }, [])

    const getTimeAgo = (dateStr: string) => {
        const diff = Date.now() - new Date(dateStr).getTime()
        const minutes = Math.floor(diff / 60000)
        if (minutes < 60) return `${minutes}m ago`
        return `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`
    }

    const getSlaRemaining = (dateStr: string) => {
        const diff = new Date(dateStr).getTime() - Date.now()
        if (diff < 0) return { text: 'Overdue', urgent: true }
        const minutes = Math.floor(diff / 60000)
        if (minutes < 15) return { text: `${minutes}m left`, urgent: true }
        return { text: `${minutes}m left`, urgent: false }
    }

    const getPriorityClass = (priority: string) => {
        switch (priority) {
            case 'high': return 'priority-high'
            case 'medium': return 'priority-medium'
            default: return 'priority-low'
        }
    }

    if (loading) {
        return <div className="loading">Loading queue...</div>
    }

    return (
        <div className="queue-page">
            <div className="page-header">
                <h1>Escalation Queue</h1>
                <span className="queue-count">{cases.length} pending</span>
            </div>

            {cases.length === 0 ? (
                <div className="empty-state">
                    <span className="empty-icon">✅</span>
                    <h3>Queue is empty</h3>
                    <p>No pending escalations. Great job!</p>
                </div>
            ) : (
                <div className="queue-list">
                    {cases.map((c) => {
                        const sla = getSlaRemaining(c.sla_deadline)
                        return (
                            <Link key={c.case_id} to={`/case/${c.case_id}`} className="case-card">
                                <div className="case-header">
                                    <span className={`priority-badge ${getPriorityClass(c.priority)}`}>
                                        {c.priority}
                                    </span>
                                    <span className={`sla-timer ${sla.urgent ? 'urgent' : ''}`}>
                                        ⏱️ {sla.text}
                                    </span>
                                </div>

                                <div className="case-customer">
                                    <span className="customer-name">{c.customer_name}</span>
                                    <span className="customer-email">{c.customer_email}</span>
                                </div>

                                <div className="case-reason">{c.reason}</div>

                                <div className="case-footer">
                                    <span className="claim-type">{c.claim_type} claim</span>
                                    <span className="created-time">{getTimeAgo(c.created_at)}</span>
                                </div>
                            </Link>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

export default QueuePage
