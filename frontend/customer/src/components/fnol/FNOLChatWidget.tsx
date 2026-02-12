import React, { useEffect, useRef, Component, ErrorInfo, ReactNode } from 'react'
import { useFNOLStore, STATE_LABELS } from '../../stores/fnolStore'
import FNOLProgressBar from './FNOLProgressBar'
import FNOLDynamicInput from './FNOLDynamicInput'
import FNOLSummaryPanel from './FNOLSummaryPanel'

/**
 * Render basic markdown (bold, italic) in a single line of text.
 * Escapes HTML first for safety, then converts markdown syntax to HTML.
 */
function renderMarkdownLine(text: string): string {
    // Escape HTML entities to prevent XSS
    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
    // Bold: **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>')
    // Italic: *text* (single asterisk, not inside bold)
    html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    // Bullet points: lines starting with • or -
    if (html.trimStart().startsWith('•') || html.trimStart().startsWith('-')) {
        html = html.replace(/^\s*[•\-]\s*/, '&bull; ')
    }
    return html
}


// Error Boundary for catching rendering errors
interface ErrorBoundaryState {
    hasError: boolean
    error?: Error
}

class FNOLErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
    constructor(props: { children: ReactNode }) {
        super(props)
        this.state = { hasError: false }
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error }
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('FNOL Widget Error:', error, errorInfo)
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="fnol-error-fallback" role="alert">
                    <h3>Something went wrong</h3>
                    <p>We're sorry, but there was an error loading the claim form.</p>
                    <button onClick={() => window.location.reload()}>
                        Reload Page
                    </button>
                    <style>{`
                        .fnol-error-fallback {
                            padding: 32px;
                            text-align: center;
                            background: #fef2f2;
                            border-radius: 12px;
                        }
                        .fnol-error-fallback h3 {
                            color: #dc2626;
                            margin: 0 0 8px;
                        }
                        .fnol-error-fallback p {
                            color: #64748b;
                            margin: 0 0 16px;
                        }
                        .fnol-error-fallback button {
                            padding: 10px 20px;
                            background: #0066cc;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                        }
                    `}</style>
                </div>
            )
        }
        return this.props.children
    }
}

interface FNOLChatWidgetProps {
    policyId?: string
    onComplete?: (claimDraftId: string) => void
    onEscalation?: (reason: string) => void
    onCancel?: () => void
}

export const FNOLChatWidget: React.FC<FNOLChatWidgetProps> = ({
    policyId,
    onComplete,
    onEscalation,
    onCancel,
}) => {
    const {
        isSessionActive,
        messages,
        currentState,
        isLoading,
        error,
        isComplete,
        shouldEscalate,
        escalationReason,
        claimDraftId,
        summary,
        showSummary,
        startSession,
        sendMessage,
        loadSummary,
        toggleSummary,
        clearError,
        resetSession,
        refreshMessages,
    } = useFNOLStore()

    const [showCancelConfirm, setShowCancelConfirm] = React.useState(false)

    const messagesEndRef = useRef<HTMLDivElement>(null)

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    // Start session on mount if not active
    useEffect(() => {
        if (!isSessionActive) {
            startSession(policyId)
        }
    }, [])

    // Handle completion and escalation callbacks
    useEffect(() => {
        if (isComplete && claimDraftId && onComplete) {
            onComplete(claimDraftId)
        }
    }, [isComplete, claimDraftId, onComplete])

    useEffect(() => {
        if (shouldEscalate && escalationReason && onEscalation) {
            onEscalation(escalationReason)
        }
    }, [shouldEscalate, escalationReason, onEscalation])

    // Load summary when reaching CLAIM_CREATE state
    useEffect(() => {
        if (currentState === 'CLAIM_CREATE' && !summary) {
            loadSummary()
        }
    }, [currentState, summary, loadSummary])

    // Poll for new messages every 3 seconds
    useEffect(() => {
        let interval: ReturnType<typeof setInterval>
        if (isSessionActive && !isComplete) {
            interval = setInterval(() => {
                refreshMessages()
            }, 1000)
        }
        return () => {
            if (interval) clearInterval(interval)
        }
    }, [isSessionActive, isComplete, refreshMessages])

    const handleSubmit = async (message: string) => {
        // Check if it's a photo upload
        if (message.startsWith('[Photo:')) {
            // This is handled separately via file input
            return
        }
        await sendMessage(message)
    }

    const handleSummaryConfirm = async () => {
        // Send confirmation message to proceed with claim creation
        await sendMessage('confirm')
    }

    const handleSummaryEdit = () => {
        // Hide summary and allow user to continue conversation
        toggleSummary()
    }

    const handleCancelClick = () => {
        setShowCancelConfirm(true)
    }

    const handleConfirmCancel = () => {
        resetSession()
        setShowCancelConfirm(false)
        if (onCancel) {
            onCancel()
        }
    }

    return (
        <div className="fnol-chat-widget" role="main" aria-label="Auto claim filing assistant">
            {/* Cancel Confirmation Modal */}
            {showCancelConfirm && (
                <div className="cancel-modal-overlay">
                    <div className="cancel-modal" role="dialog" aria-modal="true">
                        <h3>Cancel Claim?</h3>
                        <p>Are you sure you want to cancel? Your progress will be lost.</p>
                        <div className="cancel-modal-actions">
                            <button
                                className="cancel-modal-btn secondary"
                                onClick={() => setShowCancelConfirm(false)}
                            >
                                Continue Claim
                            </button>
                            <button
                                className="cancel-modal-btn danger"
                                onClick={handleConfirmCancel}
                            >
                                Yes, Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <header className="fnol-header">
                <div className="header-content">
                    <h1>File an Auto Claim</h1>
                    <span className="current-state" aria-live="polite">{STATE_LABELS[currentState]}</span>
                </div>
                <button
                    className="fnol-cancel-btn"
                    onClick={handleCancelClick}
                    aria-label="Cancel claim"
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </header>

            {/* Progress Bar */}
            <FNOLProgressBar />

            {/* Error Display */}
            {error && (
                <div className="error-banner" role="alert" aria-live="assertive">
                    <span>{error}</span>
                    <button
                        onClick={clearError}
                        className="dismiss-button"
                        aria-label="Dismiss error"
                    >
                        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                    </button>
                </div>
            )}

            {/* Summary Panel - shown when in CLAIM_CREATE state */}
            {currentState === 'CLAIM_CREATE' && summary && showSummary && (
                <div className="fnol-summary-container">
                    <FNOLSummaryPanel
                        summary={summary}
                        onConfirm={handleSummaryConfirm}
                        onEdit={handleSummaryEdit}
                        isLoading={isLoading}
                    />
                </div>
            )}

            {/* Messages */}
            <div
                className="fnol-messages"
                role="log"
                aria-label="Conversation messages"
                aria-live="polite"
                style={{ display: showSummary && currentState === 'CLAIM_CREATE' ? 'none' : 'flex' }}
            >
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`message ${message.role}`}
                        role="article"
                        aria-label={`${message.role === 'assistant' ? 'Assistant' : 'You'} said`}
                    >
                        {message.role === 'assistant' && (
                            <div className="message-avatar" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" />
                                </svg>
                            </div>
                        )}
                        <div className="message-content">
                            {message.content.split('\n').map((line, i) => (
                                <p key={i} dangerouslySetInnerHTML={{ __html: renderMarkdownLine(line) }} />
                            ))}
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="message assistant" role="status" aria-label="Assistant is typing">
                        <div className="message-avatar" aria-hidden="true">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" />
                            </svg>
                        </div>
                        <div className="message-content typing" aria-hidden="true">
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            {!isComplete && !shouldEscalate && (
                <FNOLDynamicInput onSubmit={handleSubmit} isLoading={isLoading} />
            )}

            {/* Completion Banner */}
            {isComplete && (
                <div className="completion-banner" role="status" aria-live="polite">
                    <div className="completion-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                        </svg>
                    </div>
                    <h2>Claim Submitted Successfully</h2>
                    <p>Your claim reference is: <strong>{claimDraftId?.slice(0, 8).toUpperCase()}</strong></p>
                </div>
            )}

            {/* Escalation Banner */}
            {shouldEscalate && (
                <div className="escalation-banner" role="alert" aria-live="assertive">
                    <div className="escalation-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                        </svg>
                    </div>
                    <h2>Connecting You With an Agent</h2>
                    <p>A claims specialist will assist you shortly.</p>
                </div>
            )}

            <style>{`
                .fnol-chat-widget {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    max-height: 100vh;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                }

                .fnol-summary-container {
                    flex: 1;
                    overflow-y: auto;
                    padding: 16px;
                    background: #f8fafc;
                }

                .fnol-header {
                    padding: 16px 20px;
                    background: linear-gradient(135deg, #0066cc, #0052a3);
                    color: white;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .header-content {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex: 1;
                }

                .fnol-header h1 {
                    margin: 0;
                    font-size: 18px;
                    font-weight: 600;
                }

                .current-state {
                    font-size: 13px;
                    padding: 4px 10px;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 12px;
                }

                .fnol-cancel-btn {
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border: none;
                    cursor: pointer;
                    margin-left: 12px;
                    transition: background 0.2s;
                }

                .fnol-cancel-btn:hover {
                    background: rgba(255, 255, 255, 0.3);
                }

                .fnol-cancel-btn svg {
                    width: 16px;
                    height: 16px;
                }

                .cancel-modal-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 100;
                }

                .cancel-modal {
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    max-width: 320px;
                    text-align: center;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
                }

                .cancel-modal h3 {
                    margin: 0 0 8px;
                    font-size: 18px;
                    color: #1e293b;
                }

                .cancel-modal p {
                    margin: 0 0 20px;
                    color: #64748b;
                    font-size: 14px;
                }

                .cancel-modal-actions {
                    display: flex;
                    gap: 12px;
                }

                .cancel-modal-btn {
                    flex: 1;
                    padding: 10px 16px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                    cursor: pointer;
                    border: none;
                    transition: all 0.2s;
                }

                .cancel-modal-btn.secondary {
                    background: #f1f5f9;
                    color: #475569;
                }

                .cancel-modal-btn.secondary:hover {
                    background: #e2e8f0;
                }

                .cancel-modal-btn.danger {
                    background: #dc2626;
                    color: white;
                }

                .cancel-modal-btn.danger:hover {
                    background: #b91c1c;
                }

                .error-banner {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 12px 16px;
                    background: #fef2f2;
                    border-bottom: 1px solid #fecaca;
                    color: #dc2626;
                    font-size: 14px;
                }

                .dismiss-button {
                    background: none;
                    border: none;
                    padding: 4px;
                    cursor: pointer;
                    color: #dc2626;
                }

                .dismiss-button svg {
                    width: 16px;
                    height: 16px;
                }

                .fnol-messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 16px;
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                    background: #f8fafc;
                }

                .message {
                    display: flex;
                    gap: 10px;
                    max-width: 85%;
                }

                .message.user {
                    align-self: flex-end;
                    flex-direction: row-reverse;
                }

                .message.assistant {
                    align-self: flex-start;
                }

                .message-avatar {
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    background: #e2e8f0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-shrink: 0;
                }

                .message-avatar svg {
                    width: 20px;
                    height: 20px;
                    color: #64748b;
                }

                .message-content {
                    padding: 12px 16px;
                    border-radius: 16px;
                    font-size: 14px;
                    line-height: 1.5;
                }

                .message.assistant .message-content {
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-radius: 16px 16px 16px 4px;
                }

                .message.user .message-content {
                    background: #0066cc;
                    color: white;
                    border-radius: 16px 16px 4px 16px;
                }

                .message-content p {
                    margin: 0;
                }

                .message-content p + p {
                    margin-top: 8px;
                }

                .typing {
                    display: flex;
                    gap: 4px;
                    padding: 12px 16px !important;
                }

                .typing-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #94a3b8;
                    animation: typing 1.4s infinite ease-in-out;
                }

                .typing-dot:nth-child(1) { animation-delay: 0s; }
                .typing-dot:nth-child(2) { animation-delay: 0.2s; }
                .typing-dot:nth-child(3) { animation-delay: 0.4s; }

                @keyframes typing {
                    0%, 60%, 100% { transform: translateY(0); }
                    30% { transform: translateY(-4px); }
                }

                .completion-banner,
                .escalation-banner {
                    padding: 32px 20px;
                    text-align: center;
                    background: white;
                    border-top: 1px solid #e2e8f0;
                }

                .completion-banner {
                    background: #f0fdf4;
                }

                .escalation-banner {
                    background: #fefce8;
                }

                .completion-icon,
                .escalation-icon {
                    width: 56px;
                    height: 56px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 16px;
                }

                .completion-icon {
                    background: #dcfce7;
                }

                .completion-icon svg {
                    width: 32px;
                    height: 32px;
                    color: #16a34a;
                }

                .escalation-icon {
                    background: #fef3c7;
                }

                .escalation-icon svg {
                    width: 32px;
                    height: 32px;
                    color: #ca8a04;
                }

                .completion-banner h2,
                .escalation-banner h2 {
                    margin: 0 0 8px;
                    font-size: 18px;
                    color: #1e293b;
                }

                .completion-banner p,
                .escalation-banner p {
                    margin: 0;
                    color: #64748b;
                    font-size: 14px;
                }

                @media (max-width: 480px) {
                    .message {
                        max-width: 90%;
                    }

                    .fnol-header h1 {
                        font-size: 16px;
                    }
                }
            `}</style>
        </div>
    )
}

// Wrap with error boundary for production safety
const FNOLChatWidgetWithErrorBoundary: React.FC<FNOLChatWidgetProps> = (props) => (
    <FNOLErrorBoundary>
        <FNOLChatWidget {...props} />
    </FNOLErrorBoundary>
)

export { FNOLErrorBoundary }
export default FNOLChatWidgetWithErrorBoundary
