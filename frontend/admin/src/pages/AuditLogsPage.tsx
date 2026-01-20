import { useState, useEffect } from 'react'
import { adminApi } from '../services/api'
import './AuditLogsPage.css'

interface AuditLog {
    log_id: string
    event_type: string
    actor_type: string
    actor_id: string
    resource_type: string
    resource_id: string
    details: Record<string, any>
    created_at: string
}

const EVENT_TYPES = [
    'all',
    'user.login',
    'user.signup',
    'claim.created',
    'claim.updated',
    'case.escalated',
    'settings.changed',
]

function AuditLogsPage() {
    const [logs, setLogs] = useState<AuditLog[]>([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('all')

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const data = await adminApi.getAuditLogs(100, filter === 'all' ? undefined : filter)
                setLogs(data)
            } catch (error) {
                console.error('Failed to fetch audit logs:', error)
                // Mock data for demo
                setLogs([
                    {
                        log_id: '1',
                        event_type: 'user.login',
                        actor_type: 'user',
                        actor_id: 'user-123',
                        resource_type: 'session',
                        resource_id: 'sess-456',
                        details: { ip: '192.168.1.1' },
                        created_at: new Date().toISOString(),
                    },
                    {
                        log_id: '2',
                        event_type: 'claim.created',
                        actor_type: 'user',
                        actor_id: 'user-789',
                        resource_type: 'claim',
                        resource_id: 'CLM-2024-0001',
                        details: { claim_type: 'incident', product: 'auto' },
                        created_at: new Date(Date.now() - 1800000).toISOString(),
                    },
                    {
                        log_id: '3',
                        event_type: 'settings.changed',
                        actor_type: 'admin',
                        actor_id: 'admin-001',
                        resource_type: 'settings',
                        resource_id: 'llm_provider',
                        details: { old_value: 'bedrock', new_value: 'ollama' },
                        created_at: new Date(Date.now() - 3600000).toISOString(),
                    },
                ])
            } finally {
                setLoading(false)
            }
        }
        fetchLogs()
    }, [filter])

    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr)
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        })
    }

    const getEventIcon = (eventType: string) => {
        if (eventType.startsWith('user')) return '👤'
        if (eventType.startsWith('claim')) return '📋'
        if (eventType.startsWith('case')) return '⚡'
        if (eventType.startsWith('settings')) return '⚙️'
        return '📝'
    }

    if (loading) {
        return <div className="loading">Loading audit logs...</div>
    }

    return (
        <div className="audit-logs-page">
            <div className="page-header">
                <h1>Audit Logs</h1>
                <p>System activity and security events</p>
            </div>

            <div className="filters">
                {EVENT_TYPES.map((type) => (
                    <button
                        key={type}
                        className={`filter-btn ${filter === type ? 'active' : ''}`}
                        onClick={() => setFilter(type)}
                    >
                        {type === 'all' ? 'All Events' : type}
                    </button>
                ))}
            </div>

            <div className="logs-list">
                {logs.length === 0 ? (
                    <div className="empty-state">No audit logs found</div>
                ) : (
                    logs.map((log) => (
                        <div key={log.log_id} className="log-entry">
                            <div className="log-icon">{getEventIcon(log.event_type)}</div>
                            <div className="log-content">
                                <div className="log-header">
                                    <span className="event-type">{log.event_type}</span>
                                    <span className="timestamp">{formatTime(log.created_at)}</span>
                                </div>
                                <div className="log-details">
                                    <span className="actor">{log.actor_type}: {log.actor_id}</span>
                                    <span className="separator">→</span>
                                    <span className="resource">{log.resource_type}: {log.resource_id}</span>
                                </div>
                                {Object.keys(log.details).length > 0 && (
                                    <div className="log-meta">
                                        {Object.entries(log.details).map(([key, value]) => (
                                            <span key={key} className="meta-item">
                                                {key}: {String(value)}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    )
}

export default AuditLogsPage
