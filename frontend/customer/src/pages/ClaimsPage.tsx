import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../stores/chatStore'
import { claimsApi } from '../services/api'
import './ClaimsPage.css'

interface Claim {
    claim_id: string
    claim_number: string
    policy_id: string
    claim_type: string
    status: string
    incident_date: string
    loss_amount: number
    paid_amount: number
    created_at: string
}

function ClaimsPage() {
    const { isAuthenticated } = useAuthStore()
    const { openChat } = useChatStore()
    const [claims, setClaims] = useState<Claim[]>([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('all')

    useEffect(() => {
        const fetchClaims = async () => {
            try {
                const data = await claimsApi.getMyClaims()
                setClaims(data)
            } catch (error) {
                console.error('Failed to fetch claims:', error)
            } finally {
                setLoading(false)
            }
        }

        if (isAuthenticated) {
            fetchClaims()
        }
    }, [isAuthenticated])

    if (!isAuthenticated) {
        return <Navigate to="/login" />
    }

    const filteredClaims = filter === 'all'
        ? claims
        : claims.filter(c => c.status === filter)

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'approved': return 'success'
            case 'paid': return 'success'
            case 'denied': return 'error'
            case 'under_review': return 'warning'
            case 'submitted': return 'info'
            default: return 'default'
        }
    }

    const formatCurrency = (amount: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
        }).format(amount)
    }

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
        })
    }

    return (
        <div className="claims-page">
            <div className="claims-header">
                <div>
                    <h1>My Claims</h1>
                    <p>Track and manage your insurance claims</p>
                </div>
                <button className="btn btn-primary" onClick={openChat}>
                    File New Claim
                </button>
            </div>

            <div className="claims-filters">
                <button
                    className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
                    onClick={() => setFilter('all')}
                >
                    All ({claims.length})
                </button>
                <button
                    className={`filter-btn ${filter === 'submitted' ? 'active' : ''}`}
                    onClick={() => setFilter('submitted')}
                >
                    Submitted
                </button>
                <button
                    className={`filter-btn ${filter === 'under_review' ? 'active' : ''}`}
                    onClick={() => setFilter('under_review')}
                >
                    Under Review
                </button>
                <button
                    className={`filter-btn ${filter === 'approved' ? 'active' : ''}`}
                    onClick={() => setFilter('approved')}
                >
                    Approved
                </button>
                <button
                    className={`filter-btn ${filter === 'paid' ? 'active' : ''}`}
                    onClick={() => setFilter('paid')}
                >
                    Paid
                </button>
            </div>

            {loading ? (
                <div className="loading">Loading claims...</div>
            ) : filteredClaims.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📋</div>
                    <h3>No claims found</h3>
                    <p>You don't have any claims yet. Start a conversation to file a new claim.</p>
                    <button className="btn btn-primary" onClick={openChat}>
                        File a Claim
                    </button>
                </div>
            ) : (
                <div className="claims-list">
                    {filteredClaims.map((claim) => (
                        <div key={claim.claim_id} className="claim-card">
                            <div className="claim-main">
                                <div className="claim-info">
                                    <h3 className="claim-number">{claim.claim_number}</h3>
                                    <div className="claim-type">
                                        {claim.claim_type === 'incident' ? '🚗' : '🏥'}
                                        {claim.claim_type.charAt(0).toUpperCase() + claim.claim_type.slice(1)} Claim
                                    </div>
                                </div>
                                <span className={`claim-status ${getStatusColor(claim.status)}`}>
                                    {claim.status.replace('_', ' ')}
                                </span>
                            </div>

                            <div className="claim-details">
                                <div className="claim-detail">
                                    <span className="label">Incident Date</span>
                                    <span className="value">{formatDate(claim.incident_date)}</span>
                                </div>
                                <div className="claim-detail">
                                    <span className="label">Claimed Amount</span>
                                    <span className="value">{formatCurrency(claim.loss_amount)}</span>
                                </div>
                                <div className="claim-detail">
                                    <span className="label">Paid Amount</span>
                                    <span className="value">{formatCurrency(claim.paid_amount)}</span>
                                </div>
                                <div className="claim-detail">
                                    <span className="label">Filed On</span>
                                    <span className="value">{formatDate(claim.created_at)}</span>
                                </div>
                            </div>

                            <div className="claim-actions">
                                <button className="btn btn-secondary" onClick={openChat}>
                                    Ask About This Claim
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default ClaimsPage
