import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../services/api'
import './SessionsPage.css'

interface Session {
    session_id: string
    user_id?: string
    user_name?: string
    user_email?: string
    session_type?: string
    status?: string
    thread_id?: string
    claim_draft_id?: string
    claim_number?: string
    created_at?: string
    updated_at?: string
    last_activity_at?: string
    completed_at?: string
}

function SessionsPage() {
    const [sessions, setSessions] = useState<Session[]>([])
    const [loading, setLoading] = useState(true)
    const [includeCompleted, setIncludeCompleted] = useState(true)
    const [autoRefresh, setAutoRefresh] = useState(true)
    const [searchTerm, setSearchTerm] = useState('')

    const fetchSessions = useCallback(async (isBackgroundRefresh = false) => {
        if (!isBackgroundRefresh) setLoading(true)
        try {
            const data = await adminApi.getSessions(100, includeCompleted)
            const next = data || []
            setSessions((prev) => {
                if (isBackgroundRefresh && prev.length === next.length) {
                    const same = next.every((s: Session, i: number) => prev[i]?.session_id === s.session_id && prev[i]?.updated_at === s.updated_at)
                    if (same) return prev
                }
                return next
            })
        } catch (error) {
            console.error('Failed to fetch sessions:', error)
            if (!isBackgroundRefresh) setSessions([])
        } finally {
            setLoading(false)
        }
    }, [includeCompleted])

    useEffect(() => {
        fetchSessions(false)
        let interval: ReturnType<typeof setInterval> | null = null
        if (autoRefresh) interval = setInterval(() => fetchSessions(true), 5000)
        return () => { if (interval) clearInterval(interval) }
    }, [fetchSessions, autoRefresh])

    const formatTime = (dateStr?: string) => {
        if (!dateStr) return 'Unknown'
        const date = new Date(dateStr)
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    const getStatusBadge = (status?: string) => {
        switch (status) {
            case 'active':
                return <span className="status-badge active">Active</span>
            case 'completed':
                return <span className="status-badge completed">Completed</span>
            case 'abandoned':
                return <span className="status-badge abandoned">Abandoned</span>
            default:
                return <span className="status-badge unknown">Unknown</span>
        }
    }

    const getSessionTypeIcon = (type?: string) => {
        switch (type) {
            case 'fnol':
                return '📋'
            case 'chat':
                return '💬'
            case 'inquiry':
                return '❓'
            default:
                return '💬'
        }
    }

    const filteredSessions = sessions.filter((session) => {
        if (!searchTerm) return true
        const search = searchTerm.toLowerCase()
        return (
            session.session_id?.toLowerCase().includes(search) ||
            session.user_name?.toLowerCase().includes(search) ||
            session.user_email?.toLowerCase().includes(search) ||
            session.claim_number?.toLowerCase().includes(search)
        )
    })

    if (loading) {
        return <div className="loading">Loading sessions...</div>
    }

    return (
        <div className="sessions-page">
            <div className="page-header">
                <h1>Chat Sessions</h1>
                <div className="header-controls">
                    <label className="checkbox-toggle">
                        <input
                            type="checkbox"
                            checked={includeCompleted}
                            onChange={(e) => setIncludeCompleted(e.target.checked)}
                        />
                        <span>Show completed</span>
                    </label>
                    <label className="checkbox-toggle">
                        <input
                            type="checkbox"
                            checked={autoRefresh}
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                        />
                        <span>Auto-refresh</span>
                    </label>
                    <button className="refresh-btn" onClick={fetchSessions}>
                        Refresh
                    </button>
                </div>
            </div>

            <div className="search-bar">
                <input
                    type="text"
                    placeholder="Search by session ID, user name, email, or claim number..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            <div className="sessions-stats">
                <div className="stat-card">
                    <span className="stat-label">Total Sessions</span>
                    <span className="stat-value">{sessions.length}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">Active</span>
                    <span className="stat-value">{sessions.filter(s => s.status === 'active').length}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">Completed</span>
                    <span className="stat-value">{sessions.filter(s => s.status === 'completed').length}</span>
                </div>
            </div>

            <div className="sessions-container">
                {filteredSessions.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">💬</span>
                        <p>No sessions found</p>
                        {searchTerm && <p className="empty-hint">Try a different search term</p>}
                    </div>
                ) : (
                    <div className="sessions-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Type</th>
                                    <th>Session ID</th>
                                    <th>User Name</th>
                                    <th>Email</th>
                                    <th>Status</th>
                                    <th>Claim #</th>
                                    <th>Created</th>
                                    <th>Last Activity</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredSessions.map((session) => (
                                    <tr key={session.session_id}>
                                        <td className="type-cell">
                                            <span title={session.session_type}>
                                                {getSessionTypeIcon(session.session_type)}
                                            </span>
                                        </td>
                                        <td className="session-id-cell">
                                            <span className="session-id" title={session.session_id}>
                                                {session.session_id.slice(0, 12)}...
                                            </span>
                                        </td>
                                        <td className="user-name-cell">
                                            {session.user_name || <span className="na">—</span>}
                                        </td>
                                        <td className="email-cell">
                                            {session.user_email || <span className="na">—</span>}
                                        </td>
                                        <td className="status-cell">
                                            {getStatusBadge(session.status)}
                                        </td>
                                        <td className="claim-cell">
                                            {session.claim_number || <span className="na">—</span>}
                                        </td>
                                        <td className="time-cell">
                                            {formatTime(session.created_at)}
                                        </td>
                                        <td className="time-cell">
                                            {formatTime(session.last_activity_at)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {autoRefresh && sessions.length > 0 && (
                <div className="live-indicator">
                    <span className="pulse"></span>
                    Live - Auto-refreshing every 5s
                </div>
            )}
        </div>
    )
}

export default SessionsPage
