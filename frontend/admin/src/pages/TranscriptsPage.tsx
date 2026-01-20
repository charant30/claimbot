import { useState, useEffect } from 'react'
import { adminApi } from '../services/api'
import './TranscriptsPage.css'

interface Transcript {
    thread_id: string
    user_email: string
    started_at: string
    message_count: number
    last_message: string
    was_escalated: boolean
}

function TranscriptsPage() {
    const [transcripts, setTranscripts] = useState<Transcript[]>([])
    const [loading, setLoading] = useState(true)
    const [selectedTranscript, setSelectedTranscript] = useState<string | null>(null)

    useEffect(() => {
        const fetchTranscripts = async () => {
            try {
                const data = await adminApi.getTranscripts()
                setTranscripts(data.transcripts || [])
            } catch (error) {
                console.error('Failed to fetch transcripts:', error)
                // Mock data for demo
                setTranscripts([
                    {
                        thread_id: 'thread-001',
                        user_email: 'alice@example.com',
                        started_at: new Date().toISOString(),
                        message_count: 12,
                        last_message: 'Thank you for your help with my claim!',
                        was_escalated: false,
                    },
                    {
                        thread_id: 'thread-002',
                        user_email: 'bob@example.com',
                        started_at: new Date(Date.now() - 3600000).toISOString(),
                        message_count: 8,
                        last_message: 'I need to speak with someone about my policy.',
                        was_escalated: true,
                    },
                ])
            } finally {
                setLoading(false)
            }
        }
        fetchTranscripts()
    }, [])

    const formatTime = (dateStr: string) => {
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
                <h1>Chat Transcripts</h1>
                <p>Review conversation histories</p>
            </div>

            <div className="transcripts-list">
                {transcripts.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">💬</span>
                        <p>No transcripts available</p>
                    </div>
                ) : (
                    transcripts.map((transcript) => (
                        <div
                            key={transcript.thread_id}
                            className={`transcript-card ${selectedTranscript === transcript.thread_id ? 'selected' : ''}`}
                            onClick={() => setSelectedTranscript(transcript.thread_id)}
                        >
                            <div className="transcript-header">
                                <span className="user-email">{transcript.user_email}</span>
                                <span className="timestamp">{formatTime(transcript.started_at)}</span>
                            </div>
                            <p className="last-message">{transcript.last_message}</p>
                            <div className="transcript-footer">
                                <span className="message-count">{transcript.message_count} messages</span>
                                {transcript.was_escalated && (
                                    <span className="escalated-badge">Escalated</span>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>

            <div className="info-box">
                <span className="info-icon">ℹ️</span>
                <p>
                    Click on a transcript to view the full conversation.
                    Transcript viewing is currently in development.
                </p>
            </div>
        </div>
    )
}

export default TranscriptsPage
