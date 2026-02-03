import { useState, useRef, useEffect } from 'react'
import { useChatStore, PRODUCT_OPTIONS, INTENT_OPTIONS } from '../stores/chatStore'
import { useAuthStore } from '../stores/authStore'
import GuestForm from './GuestForm'
import ClaimIntakeForm from './ClaimIntakeForm'
import DocumentUploadPanel from './DocumentUploadPanel'
import './ChatWidget.css'

function ChatWidget() {
    const {
        isOpen, toggleChat, messages, isLoading, sendMessage,
        startSession, threadId, flowStage, selectProduct, selectIntent,
        submitClaimForm, uploadDocument, claimId, documents
    } = useChatStore()
    const { isAuthenticated } = useAuthStore()
    const [input, setInput] = useState('')
    const [showGuestForm, setShowGuestForm] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleOpen = async () => {
        toggleChat()
        if (!isOpen && !threadId) {
            if (isAuthenticated) {
                await startSession()
            } else {
                setShowGuestForm(true)
            }
        }
    }

    const handleGuestSubmit = async () => {
        setShowGuestForm(false)
        await startSession()
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!input.trim() || isLoading) return

        const message = input.trim()
        setInput('')
        await sendMessage(message)
    }

    const handleProductSelect = (productId: string) => {
        selectProduct(productId)
    }

    const handleIntentSelect = async (intentId: string) => {
        await selectIntent(intentId)
    }

    return (
        <>
            {/* Chat toggle button */}
            <button className="chat-toggle" onClick={handleOpen} aria-label="Toggle chat">
                {isOpen ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M6 18L18 6M6 6l12 12" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                    </svg>
                )}
            </button>

            {/* Chat window */}
            <div className={`chat-widget ${isOpen ? 'open' : ''}`}>
                <div className="chat-header">
                    <div className="chat-header-info">
                        <div className="chat-avatar">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                            </svg>
                        </div>
                        <div>
                            <h3 className="chat-title">ClaimBot</h3>
                            <p className="chat-subtitle">Insurance Assistant</p>
                        </div>
                    </div>
                    <button className="chat-close" onClick={toggleChat}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {showGuestForm ? (
                    <GuestForm onSubmit={handleGuestSubmit} />
                ) : (
                    <>
                        <div className="chat-messages">
                            {messages.map((msg) => (
                                <div key={msg.id} className={`message ${msg.role}`}>
                                    <div className="message-content">{msg.content}</div>
                                </div>
                            ))}

                            {/* Product Selection Buttons */}
                            {flowStage === 'product_selection' && !isLoading && messages.length > 0 && (
                                <div className="selection-buttons">
                                    {PRODUCT_OPTIONS.map((option) => (
                                        <button
                                            key={option.id}
                                            className="selection-btn product-btn"
                                            onClick={() => handleProductSelect(option.id)}
                                        >
                                            <span className="btn-icon">{option.icon}</span>
                                            <span className="btn-label">{option.label}</span>
                                        </button>
                                    ))}
                                </div>
                            )}

                            {/* Intent Selection Buttons */}
                            {flowStage === 'intent_selection' && !isLoading && (
                                <div className="selection-buttons intent-buttons">
                                    {INTENT_OPTIONS.map((option) => (
                                        <button
                                            key={option.id}
                                            className="selection-btn intent-btn"
                                            onClick={() => handleIntentSelect(option.id)}
                                        >
                                            <span className="btn-icon">{option.icon}</span>
                                            <span className="btn-label">{option.label}</span>
                                        </button>
                                    ))}
                                </div>
                            )}

                            {flowStage === 'claim_form' && (
                                <ClaimIntakeForm onSubmit={submitClaimForm} isLoading={isLoading} />
                            )}

                            {/* Show document upload panel in document_upload stage */}
                            {flowStage === 'document_upload' && claimId && (
                                <DocumentUploadPanel
                                    claimId={claimId}
                                    documents={documents}
                                    isLoading={isLoading}
                                    onUpload={uploadDocument}
                                />
                            )}

                            {/* In conversation mode, show compact document panel if claim exists but photos not yet uploaded */}
                            {flowStage === 'conversation' && claimId && !documents.some(d => d.doc_type === 'incident_photos') && (
                                <div className="document-reminder">
                                    <p>Please upload incident photos to continue with your claim.</p>
                                    <DocumentUploadPanel
                                        claimId={claimId}
                                        documents={documents}
                                        isLoading={isLoading}
                                        onUpload={uploadDocument}
                                    />
                                </div>
                            )}

                            {isLoading && (
                                <div className="message assistant">
                                    <div className="message-content typing">
                                        <span></span><span></span><span></span>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Only show input when in conversation mode */}
                        {(flowStage === 'conversation' || flowStage === 'document_upload') && (
                            <form className="chat-input-form" onSubmit={handleSubmit}>
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Type your message..."
                                    className="chat-input"
                                    disabled={isLoading}
                                />
                                <button type="submit" className="chat-send" disabled={isLoading || !input.trim()}>
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                                    </svg>
                                </button>
                            </form>
                        )}
                    </>
                )}
            </div>
        </>
    )
}

export default ChatWidget
