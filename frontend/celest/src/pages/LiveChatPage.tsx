import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { handoffApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import './LiveChatPage.css'

interface Message {
    id: string
    role: 'user' | 'agent' | 'ai'
    content: string
    sender_name: string
    timestamp: string
}

function LiveChatPage() {
    const { caseId } = useParams()
    const navigate = useNavigate()
    const { user } = useAuthStore()
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(true)
    const [sending, setSending] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const isInitialLoadRef = useRef(true)

    const fetchMessages = async (isBackgroundRefresh = false) => {
        try {
            const data: any[] = await handoffApi.getMessages(caseId!)
            const mappedMessages: Message[] = data.map((msg, index) => ({
                id: msg.message_id || `msg-${index}-${msg.created_at || ''}`,
                role: msg.role as 'user' | 'agent' | 'ai',
                content: msg.content,
                sender_name: msg.role === 'user' ? 'Customer' : msg.role === 'agent' ? 'Agent' : 'ClaimBot AI',
                timestamp: msg.created_at || new Date().toISOString()
            }))

            setMessages((prev) => {
                if (isBackgroundRefresh && prev.length > 0) {
                    const sameLength = mappedMessages.length === prev.length
                    const sameIds = sameLength && mappedMessages.every((m, i) => prev[i]?.id === m.id)
                    const sameContent = sameLength && mappedMessages.every((m, i) => prev[i]?.content === m.content)
                    if (sameIds && sameContent) return prev
                    if (mappedMessages.length < prev.length) return prev
                }
                return mappedMessages
            })
        } catch (error) {
            console.error('Failed to fetch messages:', error)
        } finally {
            setLoading(false)
        }
    }

    // Initial fetch then poll in background without replacing state if unchanged
    useEffect(() => {
        isInitialLoadRef.current = true
        fetchMessages(false)
        const interval = setInterval(() => fetchMessages(true), 3000)
        return () => clearInterval(interval)
    }, [caseId])

    // Scroll to bottom only on initial load or when user sends a message (handled after send)
    useEffect(() => {
        if (!isInitialLoadRef.current) return
        if (loading) return
        isInitialLoadRef.current = false
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [loading, messages.length])

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!input.trim() || sending) return

        const content = input.trim()
        setInput('')
        setSending(true)

        // Add message optimistically
        const newMessage: Message = {
            id: `temp-${Date.now()}`,
            role: 'agent',
            content,
            sender_name: user?.name || 'Claims Specialist',
            timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, newMessage])
        requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }))

        try {
            await handoffApi.sendMessage(caseId!, content)
        } catch (error) {
            console.error('Failed to send message:', error)
        } finally {
            setSending(false)
        }
    }

    const handleRelease = async () => {
        try {
            await handoffApi.releaseCase(caseId!)
            navigate('/')
        } catch (error) {
            console.error('Failed to release case:', error)
        }
    }

    const formatTime = (dateStr: string) => {
        return new Date(dateStr).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    if (loading) {
        return <div className="loading">Loading chat...</div>
    }

    return (
        <div className="live-chat-page">
            <div className="chat-header">
                <Link to={`/case/${caseId}`} className="back-link">← Back to Case</Link>
                <div className="chat-title">
                    <h1>Live Chat Takeover</h1>
                    <span className="active-badge">🔴 Live</span>
                </div>
                <button className="btn btn-secondary" onClick={handleRelease}>
                    Release to AI
                </button>
            </div>

            <div className="chat-container">
                <div className="messages-panel">
                    {messages.map((msg) => (
                        <div key={msg.id} className={`chat-message ${msg.role}`}>
                            <div className="message-header">
                                <span className="sender">{msg.sender_name}</span>
                                <span className="time">{formatTime(msg.timestamp)}</span>
                            </div>
                            <div className="message-content">{msg.content}</div>
                        </div>
                    ))}
                    <div ref={messagesEndRef} />
                </div>

                <form className="chat-input-form" onSubmit={handleSend}>
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Type your message to the customer..."
                        disabled={sending}
                    />
                    <button type="submit" className="btn btn-primary" disabled={sending || !input.trim()}>
                        Send
                    </button>
                </form>
            </div>

            <div className="quick-responses">
                <h3>Quick Responses</h3>
                <div className="response-buttons">
                    <button onClick={() => setInput("I've reviewed your claim and everything looks good. Let me process this for you.")}>
                        Approve Response
                    </button>
                    <button onClick={() => setInput("I need a bit more information to process your claim. Could you please provide...")}>
                        Request Info
                    </button>
                    <button onClick={() => setInput("Thank you for your patience. I'm looking into this now.")}>
                        Acknowledge
                    </button>
                </div>
            </div>
        </div>
    )
}

export default LiveChatPage
