import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../stores/chatStore'
import { policiesApi } from '../services/api'
import './DashboardPage.css'

interface Policy {
    policy_id: string
    policy_number: string
    product_type: string
    effective_date: string
    expiration_date: string
    status: string
    is_active: boolean
}

function DashboardPage() {
    const { isAuthenticated, user } = useAuthStore()
    const { openChat, setPolicyId } = useChatStore()
    const [policies, setPolicies] = useState<Policy[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchPolicies = async () => {
            try {
                const data = await policiesApi.getMyPolicies()
                setPolicies(data)
            } catch (error) {
                console.error('Failed to fetch policies:', error)
            } finally {
                setLoading(false)
            }
        }

        if (isAuthenticated) {
            fetchPolicies()
        }
    }, [isAuthenticated])

    if (!isAuthenticated) {
        return <Navigate to="/login" />
    }

    const handleFileClaimForPolicy = (policyId: string) => {
        setPolicyId(policyId)
        openChat()
    }

    const getProductIcon = (type: string) => {
        switch (type) {
            case 'auto': return '🚗'
            case 'home': return '🏠'
            case 'medical': return '🏥'
            default: return '📋'
        }
    }

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
        })
    }

    return (
        <div className="dashboard-page">
            <div className="dashboard-header">
                <div>
                    <h1>Welcome, {user?.name?.split(' ')[0] || 'User'}</h1>
                    <p>Manage your policies and claims</p>
                </div>
                <button className="btn btn-primary" onClick={openChat}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                    </svg>
                    Chat with ClaimBot
                </button>
            </div>

            <section className="policies-section">
                <h2>Your Policies</h2>

                {loading ? (
                    <div className="loading">Loading policies...</div>
                ) : policies.length === 0 ? (
                    <div className="empty-state">
                        <p>No policies found. Contact support if this is unexpected.</p>
                    </div>
                ) : (
                    <div className="policies-grid">
                        {policies.map((policy) => (
                            <div key={policy.policy_id} className={`policy-card ${!policy.is_active ? 'inactive' : ''}`}>
                                <div className="policy-header">
                                    <span className="policy-icon">{getProductIcon(policy.product_type)}</span>
                                    <span className={`policy-status ${policy.is_active ? 'active' : 'inactive'}`}>
                                        {policy.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </div>
                                <h3 className="policy-type">{policy.product_type.charAt(0).toUpperCase() + policy.product_type.slice(1)} Insurance</h3>
                                <p className="policy-number">{policy.policy_number}</p>
                                <div className="policy-dates">
                                    <span>{formatDate(policy.effective_date)} - {formatDate(policy.expiration_date)}</span>
                                </div>
                                <div className="policy-actions">
                                    <button
                                        className="btn btn-secondary"
                                        onClick={() => handleFileClaimForPolicy(policy.policy_id)}
                                        disabled={!policy.is_active}
                                    >
                                        File Claim
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section className="quick-actions">
                <h2>Quick Actions</h2>
                <div className="actions-grid">
                    <button className="action-card" onClick={openChat}>
                        <div className="action-icon">📋</div>
                        <h3>File a Claim</h3>
                        <p>Start a new claim for any policy</p>
                    </button>
                    <a href="/claims" className="action-card">
                        <div className="action-icon">🔍</div>
                        <h3>View Claims</h3>
                        <p>Check status of existing claims</p>
                    </a>
                    <button className="action-card" onClick={openChat}>
                        <div className="action-icon">💬</div>
                        <h3>Get Help</h3>
                        <p>Ask questions about your coverage</p>
                    </button>
                </div>
            </section>
        </div>
    )
}

export default DashboardPage
