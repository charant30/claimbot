import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '../services/api'
import './TranscriptsPage.css'

interface Transcript {
    thread_id: string
    user_id: string
    policy_id?: string
    message_count: number
    created_at: string
    last_message?: string
}

interface TranscriptDetail {
    thread_id: string
    user_id: string
    policy_id?: string
    messages: Array<{
        message_id?: string
        role: 'user' | 'assistant'
        content: string
        metadata?: Record<string, any>
    }>
    created_at: string
}

function TranscriptsPage() {
    const [transcripts, setTranscripts] = useState<Transcript[]>([])
    const [loading, setLoading] = useState(true)
    const [selectedTranscript, setSelectedTranscript] = useState<string | null>(null)
    const [transcriptDetail, setTranscriptDetail] = useState<TranscriptDetail | null>(null)
    const [loadingDetail, setLoadingDetail] = useState(false)
    const [autoRefresh, setAutoRefresh] = useState(true)

    const fetchTranscripts = useCallback(async () => {
        try {
            const data = await adminApi.getTranscripts(50)
            setTranscripts(data || [])
        } catch (error) {
            console.error('Failed to fetch transcripts:', error)
            setTranscripts([])
        } finally {
            setLoading(false)
        }
    }, [])

    // Initial fetch and auto-refresh
    useEffect(() => {
        fetchTranscripts()

        // Auto-refresh every 5 seconds if enabled
        let interval: ReturnType<typeof setInterval> | null = null
        if (autoRefresh) {
            interval = setInterval(fetchTranscripts, 5000)
        }

        return () => {
            if (interval) clearInterval(interval)
        }
    }, [fetchTranscripts, autoRefresh])

    // Fetch transcript detail when selected
    useEffect(() => {
        if (!selectedTranscript) {
            setTranscriptDetail(null)
            return
        }

        const fetchDetail = async () => {
            setLoadingDetail(true)
            try {
                const detail = await adminApi.getTranscriptDetail(selectedTranscript)
                setTranscriptDetail(detail)
            } catch (error) {
                console.error('Failed to fetch transcript detail:', error)
                setTranscriptDetail(null)
            } finally {
                setLoadingDetail(false)
            }
        }

        fetchDetail()

        // Auto-refresh detail if viewing live
        let interval: ReturnType<typeof setInterval> | null = null
        if (autoRefresh) {
            interval = setInterval(fetchDetail, 3000)
        }

        return () => {
            if (interval) clearInterval(interval)
        }
    }, [selectedTranscript, autoRefresh])

    const formatTime = (dateStr: string) => {
        if (!dateStr) return 'Unknown'
        const date = new Date(dateStr)
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    if (loading) {
        return <div className="loading">Loading transcripts...</div>
    }

    return (
        <div className="transcripts-page">
            <div className="page-header">
                <h1>Live Chat Transcripts</h1>
                <div className="header-controls">
                    <label className="auto-refresh-toggle">
                        <input
                            type="checkbox"
                            checked={autoRefresh}
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                        />
                        <span>Auto-refresh (live view)</span>
                    </label>
                    <button className="refresh-btn" onClick={fetchTranscripts}>
                        Refresh
                    </button>
                </div>
            </div>

            <div className="transcripts-container">
                {/* Transcript List */}
                <div className="transcripts-list">
                    <h3>Sessions ({transcripts.length})</h3>
                    {transcripts.length === 0 ? (
                        <div className="empty-state">
                            <span className="empty-icon">💬</span>
                            <p>No active sessions</p>
                        </div>
                    ) : (
                        transcripts.map((transcript) => (
                            <div
                                key={transcript.thread_id}
                                className={`transcript-card ${selectedTranscript === transcript.thread_id ? 'selected' : ''}`}
                                onClick={() => setSelectedTranscript(transcript.thread_id)}
                            >
                                <div className="transcript-header">
                                    <span className="thread-id">{transcript.thread_id.slice(0, 8)}...</span>
                                    <span className="timestamp">{formatTime(transcript.created_at)}</span>
                                </div>
                                <p className="last-message">{transcript.last_message || 'No messages yet'}</p>
                                <div className="transcript-footer">
                                    <span className="message-count">{transcript.message_count} messages</span>
                                    {transcript.policy_id && (
                                        <span className="policy-badge">Has Policy</span>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* Transcript Detail View */}
                <div className="transcript-detail">
                    {!selectedTranscript ? (
                        <div className="empty-detail">
                            <span className="empty-icon">👈</span>
                            <p>Select a session to view the conversation</p>
                        </div>
                    ) : loadingDetail ? (
                        <div className="loading-detail">Loading messages...</div>
                    ) : transcriptDetail ? (
                        <>
                            <div className="detail-header">
                                <h3>Conversation</h3>
                                <div className="detail-meta">
                                    <span>Thread: {transcriptDetail.thread_id.slice(0, 12)}...</span>
                                    <span>User: {transcriptDetail.user_id.slice(0, 12)}...</span>
                                    {transcriptDetail.policy_id && (
                                        <span>Policy: {transcriptDetail.policy_id.slice(0, 8)}...</span>
                                    )}
                                </div>
                            </div>
                            <div className="messages-container">
                                {transcriptDetail.messages.length === 0 ? (
                                    <p className="no-messages">No messages in this session</p>
                                ) : (
                                    transcriptDetail.messages.map((msg, idx) => (
                                        <div key={msg.message_id || idx} className={`message ${msg.role}`}>
                                            <div className="message-role">{msg.role === 'user' ? 'Customer' : 'ClaimBot'}</div>
                                            <div className="message-content">{msg.content}</div>
                                            {msg.metadata && Object.keys(msg.metadata).length > 0 && (
                                                <div className="message-metadata">
                                                    {msg.metadata.intent && <span>Intent: {msg.metadata.intent}</span>}
                                                    {msg.metadata.product_line && <span>Product: {msg.metadata.product_line}</span>}
                                                    {msg.metadata.should_escalate && <span className="escalate-flag">Escalated</span>}
                                                </div>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                            {autoRefresh && (
                                <div className="live-indicator">
                                    <span className="pulse"></span>
                                    Live - Auto-refreshing every 3s
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="error-detail">Failed to load transcript</div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default TranscriptsPage
