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
    const [error, setError] = useState<string | null>(null)

    const fetchQueue = async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await handoffApi.getQueue()
            setCases(Array.isArray(data) ? data : [])
        } catch (err: any) {
            console.error('Failed to fetch queue:', err)
            const status = err.response?.status
            if (status === 401) {
                setError('Authentication expired. Please log in again.')
            } else if (status === 403) {
                setError('You do not have permission to view the queue.')
            } else {
                setError('Failed to load escalation queue. Please try again.')
            }
            setCases([])
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
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
                <div className="header-actions">
                    <span className="queue-count">{cases.length} pending</span>
                    <button className="btn btn-secondary" onClick={fetchQueue}>
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div className="queue-error">
                    <span className="error-icon">⚠️</span>
                    <div>
                        <h3>Unable to Load Queue</h3>
                        <p>{error}</p>
                    </div>
                    <button className="btn btn-primary" onClick={fetchQueue}>
                        Retry
                    </button>
                </div>
            )}

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
