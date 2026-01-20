import { useState, useEffect } from 'react'
import { adminApi } from '../services/api'
import './FlowsPage.css'

interface Intent {
    name: string
    description: string
    examples: string[]
}

interface FlowRule {
    intent: string
    product_lines: string[]
    requires_auth: boolean
    escalation_threshold: number
}

function FlowsPage() {
    const [intents, setIntents] = useState<Intent[]>([])
    const [flows, setFlows] = useState<FlowRule[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [intentsData, flowsData] = await Promise.all([
                    adminApi.getIntents(),
                    adminApi.getFlows(),
                ])
                setIntents(intentsData.intents || [])
                setFlows(flowsData.rules || [])
            } catch (error) {
                console.error('Failed to fetch flows:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchData()
    }, [])

    if (loading) {
        return <div className="loading">Loading flows...</div>
    }

    return (
        <div className="flows-page">
            <div className="page-header">
                <h1>Flows & Intents</h1>
                <p>Configure chat intents and routing rules</p>
            </div>

            {/* Intents Section */}
            <section className="section">
                <div className="section-header">
                    <h2>Intents</h2>
                    <span className="badge">{intents.length} configured</span>
                </div>
                <div className="intents-grid">
                    {intents.map((intent) => (
                        <div key={intent.name} className="intent-card">
                            <h3>{intent.name}</h3>
                            <p>{intent.description}</p>
                            <div className="examples">
                                <strong>Examples:</strong>
                                <ul>
                                    {intent.examples.slice(0, 3).map((ex, i) => (
                                        <li key={i}>"{ex}"</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* Flow Rules Section */}
            <section className="section">
                <div className="section-header">
                    <h2>Routing Rules</h2>
                    <span className="badge">{flows.length} rules</span>
                </div>
                <div className="rules-table">
                    <div className="table-header">
                        <span>Intent</span>
                        <span>Product Lines</span>
                        <span>Auth Required</span>
                        <span>Escalation Threshold</span>
                    </div>
                    {flows.map((rule, index) => (
                        <div key={index} className="table-row">
                            <span className="intent-name">{rule.intent}</span>
                            <span className="products">
                                {rule.product_lines.map(p => (
                                    <span key={p} className="product-tag">{p}</span>
                                ))}
                            </span>
                            <span className={`auth-badge ${rule.requires_auth ? 'required' : 'optional'}`}>
                                {rule.requires_auth ? 'Required' : 'Optional'}
                            </span>
                            <span className="threshold">
                                <div className="threshold-bar" style={{ width: `${rule.escalation_threshold}%` }} />
                                {rule.escalation_threshold}%
                            </span>
                        </div>
                    ))}
                </div>
            </section>

            <div className="info-box">
                <span className="info-icon">ℹ️</span>
                <p>
                    Flow rules are currently read-only. To modify intents or routing rules,
                    edit the configuration files in the backend.
                </p>
            </div>
        </div>
    )
}

export default FlowsPage
