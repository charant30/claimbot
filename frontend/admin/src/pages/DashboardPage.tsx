import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { adminApi } from '../services/api'
import './DashboardPage.css'

interface Metrics {
    total_users: number
    total_claims: number
    active_cases: number
    resolved_cases: number
    claims_by_status: Record<string, number>
    escalation_rate: number
}

const STATUS_COLORS: Record<string, string> = {
    draft: '#64748b',
    submitted: '#3b82f6',
    under_review: '#f59e0b',
    approved: '#22c55e',
    denied: '#ef4444',
    paid: '#10b981',
}

function DashboardPage() {
    const [metrics, setMetrics] = useState<Metrics | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const data = await adminApi.getMetrics()
                setMetrics(data)
            } catch (error) {
                console.error('Failed to fetch metrics:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchMetrics()
    }, [])

    if (loading) {
        return <div className="loading">Loading dashboard...</div>
    }

    const claimsStatusData = metrics ?
        Object.entries(metrics.claims_by_status)
            .filter(([_, value]) => value > 0)
            .map(([status, count]) => ({
                name: status.replace('_', ' '),
                value: count,
                color: STATUS_COLORS[status] || '#64748b',
            })) : []

    return (
        <div className="dashboard-page">
            <div className="page-header">
                <h1>Dashboard</h1>
                <p>System overview and key metrics</p>
            </div>

            {/* Stats Cards */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon">👥</div>
                    <div className="stat-content">
                        <span className="stat-value">{metrics?.total_users || 0}</span>
                        <span className="stat-label">Total Users</span>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">📋</div>
                    <div className="stat-content">
                        <span className="stat-value">{metrics?.total_claims || 0}</span>
                        <span className="stat-label">Total Claims</span>
                    </div>
                </div>
                <div className="stat-card highlight">
                    <div className="stat-icon">⚡</div>
                    <div className="stat-content">
                        <span className="stat-value">{metrics?.active_cases || 0}</span>
                        <span className="stat-label">Active Cases</span>
                    </div>
                </div>
                <div className="stat-card success">
                    <div className="stat-icon">✅</div>
                    <div className="stat-content">
                        <span className="stat-value">{metrics?.resolved_cases || 0}</span>
                        <span className="stat-label">Resolved Cases</span>
                    </div>
                </div>
            </div>

            {/* Charts Row */}
            <div className="charts-grid">
                <div className="chart-card">
                    <h3>Claims by Status</h3>
                    <div className="chart-container">
                        <ResponsiveContainer width="100%" height={250}>
                            <BarChart data={claimsStatusData}>
                                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{
                                        background: '#1e293b',
                                        border: '1px solid #334155',
                                        borderRadius: '8px',
                                    }}
                                />
                                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                    {claimsStatusData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="chart-card">
                    <h3>Escalation Rate</h3>
                    <div className="escalation-display">
                        <div className="escalation-value">
                            <span className="big-number">{metrics?.escalation_rate || 0}%</span>
                            <span className="label">of claims escalated</span>
                        </div>
                        <div className="escalation-breakdown">
                            <div className="breakdown-item">
                                <span className="dot ai"></span>
                                <span>AI Handled: {100 - (metrics?.escalation_rate || 0)}%</span>
                            </div>
                            <div className="breakdown-item">
                                <span className="dot human"></span>
                                <span>Human Review: {metrics?.escalation_rate || 0}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Quick Links */}
            <div className="quick-links">
                <h3>Quick Actions</h3>
                <div className="links-grid">
                    <a href="/llm-settings" className="link-card">
                        <span className="link-icon">🤖</span>
                        <span>Configure LLM</span>
                    </a>
                    <a href="/flows" className="link-card">
                        <span className="link-icon">🔀</span>
                        <span>Manage Flows</span>
                    </a>
                    <a href="/audit-logs" className="link-card">
                        <span className="link-icon">📋</span>
                        <span>View Audit Logs</span>
                    </a>
                    <a href="/transcripts" className="link-card">
                        <span className="link-icon">💬</span>
                        <span>View Transcripts</span>
                    </a>
                </div>
            </div>
        </div>
    )
}

export default DashboardPage
