import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FNOLChatWidget } from '../components/fnol'
import { useAuthStore } from '../stores/authStore'
import { useFNOLStore } from '../stores/fnolStore'

export const FNOLPage: React.FC = () => {
    const navigate = useNavigate()
    const { user } = useAuthStore()
    const { resetSession } = useFNOLStore()
    const [showConfirmation, setShowConfirmation] = useState(false)
    const [completedClaimId, setCompletedClaimId] = useState<string | null>(null)
    const [showEscalation, setShowEscalation] = useState(false)
    const [escalationReason, setEscalationReason] = useState<string | null>(null)

    const handleComplete = (claimDraftId: string) => {
        setCompletedClaimId(claimDraftId)
        setShowConfirmation(true)
    }

    const handleEscalation = (reason: string) => {
        setEscalationReason(reason)
        setShowEscalation(true)
    }

    const handleViewClaims = () => {
        navigate('/claims')
    }

    const handleFileAnother = () => {
        resetSession()
        setShowConfirmation(false)
        setCompletedClaimId(null)
    }

    const handleReturnHome = () => {
        navigate('/')
    }

    const handleCancel = () => {
        navigate('/')
    }

    // Confirmation screen after successful claim submission
    if (showConfirmation && completedClaimId) {
        return (
            <div className="fnol-page">
                <div className="fnol-confirmation">
                    <div className="confirmation-content">
                        <div className="confirmation-icon">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                            </svg>
                        </div>
                        <h1>Claim Submitted Successfully!</h1>
                        <p className="claim-reference">
                            Your claim reference number is:
                            <strong>{completedClaimId.slice(0, 8).toUpperCase()}</strong>
                        </p>
                        <p className="next-steps">
                            We've received your claim and our team will review it shortly.
                            You'll receive updates via email and can track the status in your dashboard.
                        </p>
                        <div className="confirmation-actions">
                            <button className="btn-primary" onClick={handleViewClaims}>
                                View My Claims
                            </button>
                            <button className="btn-secondary" onClick={handleFileAnother}>
                                File Another Claim
                            </button>
                            <button className="btn-tertiary" onClick={handleReturnHome}>
                                Return Home
                            </button>
                        </div>
                    </div>
                </div>
                <style>{confirmationStyles}</style>
            </div>
        )
    }

    // Escalation screen when agent handoff is triggered
    if (showEscalation) {
        return (
            <div className="fnol-page">
                <div className="fnol-escalation">
                    <div className="escalation-content">
                        <div className="escalation-icon">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                            </svg>
                        </div>
                        <h1>Connecting You With an Agent</h1>
                        <p className="escalation-reason">
                            {escalationReason || 'Your claim requires additional attention from a claims specialist.'}
                        </p>
                        <div className="waiting-indicator">
                            <div className="pulse-ring"></div>
                            <span>Please wait while we connect you...</span>
                        </div>
                        <p className="contact-info">
                            If you prefer, you can also call us directly at <strong>1-800-CLAIMS</strong>
                        </p>
                        <button className="btn-secondary" onClick={handleReturnHome}>
                            Return Home
                        </button>
                    </div>
                </div>
                <style>{escalationStyles}</style>
            </div>
        )
    }

    return (
        <div className="fnol-page">
            <div className="fnol-container">
                <FNOLChatWidget
                    policyId={user?.policyId}
                    onComplete={handleComplete}
                    onEscalation={handleEscalation}
                    onCancel={handleCancel}
                />
            </div>

            <style>{pageStyles}</style>
        </div>
    )
}

const pageStyles = `
    .fnol-page {
        min-height: 100vh;
        background: #f1f5f9;
        padding: 20px;
    }

    .fnol-container {
        max-width: 600px;
        margin: 0 auto;
        height: calc(100vh - 40px);
    }

    @media (max-width: 640px) {
        .fnol-page {
            padding: 0;
        }

        .fnol-container {
            max-width: 100%;
            height: 100vh;
            border-radius: 0;
        }
    }
`

const confirmationStyles = `
    ${pageStyles}

    .fnol-confirmation {
        max-width: 500px;
        margin: 0 auto;
        padding-top: 60px;
    }

    .confirmation-content {
        background: white;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    .confirmation-icon {
        width: 80px;
        height: 80px;
        background: #dcfce7;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px;
    }

    .confirmation-icon svg {
        width: 48px;
        height: 48px;
        color: #16a34a;
    }

    .confirmation-content h1 {
        margin: 0 0 16px;
        font-size: 24px;
        color: #1e293b;
    }

    .claim-reference {
        background: #f8fafc;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        font-size: 14px;
        color: #64748b;
    }

    .claim-reference strong {
        display: block;
        font-size: 20px;
        color: #0066cc;
        margin-top: 4px;
        font-family: monospace;
        letter-spacing: 1px;
    }

    .next-steps {
        color: #64748b;
        font-size: 14px;
        line-height: 1.6;
        margin-bottom: 32px;
    }

    .confirmation-actions {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .btn-primary,
    .btn-secondary,
    .btn-tertiary {
        padding: 14px 24px;
        border-radius: 8px;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        border: none;
    }

    .btn-primary {
        background: #0066cc;
        color: white;
    }

    .btn-primary:hover {
        background: #0052a3;
    }

    .btn-secondary {
        background: white;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    .btn-secondary:hover {
        background: #f8fafc;
        border-color: #cbd5e1;
    }

    .btn-tertiary {
        background: transparent;
        color: #64748b;
    }

    .btn-tertiary:hover {
        color: #1e293b;
    }
`

const escalationStyles = `
    ${pageStyles}

    .fnol-escalation {
        max-width: 500px;
        margin: 0 auto;
        padding-top: 60px;
    }

    .escalation-content {
        background: white;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    .escalation-icon {
        width: 80px;
        height: 80px;
        background: #fef3c7;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px;
    }

    .escalation-icon svg {
        width: 48px;
        height: 48px;
        color: #ca8a04;
    }

    .escalation-content h1 {
        margin: 0 0 16px;
        font-size: 24px;
        color: #1e293b;
    }

    .escalation-reason {
        color: #64748b;
        font-size: 14px;
        line-height: 1.6;
        margin-bottom: 24px;
    }

    .waiting-indicator {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 16px;
        margin-bottom: 24px;
        padding: 20px;
        background: #f8fafc;
        border-radius: 8px;
    }

    .pulse-ring {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #0066cc;
        animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
        0% {
            transform: scale(0.9);
            opacity: 1;
        }
        50% {
            transform: scale(1.1);
            opacity: 0.7;
        }
        100% {
            transform: scale(0.9);
            opacity: 1;
        }
    }

    .waiting-indicator span {
        color: #64748b;
        font-size: 14px;
    }

    .contact-info {
        color: #64748b;
        font-size: 14px;
        margin-bottom: 24px;
    }

    .contact-info strong {
        color: #0066cc;
    }

    .btn-secondary {
        padding: 14px 24px;
        border-radius: 8px;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        background: white;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    .btn-secondary:hover {
        background: #f8fafc;
        border-color: #cbd5e1;
    }
`

export default FNOLPage
