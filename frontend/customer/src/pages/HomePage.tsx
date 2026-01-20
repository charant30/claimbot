import { useChatStore } from '../stores/chatStore'
import './HomePage.css'

function HomePage() {
    const { openChat } = useChatStore()

    return (
        <div className="home-page">
            {/* Hero Section */}
            <section className="hero">
                <div className="hero-content">
                    <h1 className="hero-title">
                        Insurance Claims <span className="gradient-text">Made Simple</span>
                    </h1>
                    <p className="hero-subtitle">
                        File claims, check status, and get answers instantly with our AI-powered assistant.
                        Available 24/7 to help you navigate your insurance needs.
                    </p>
                    <div className="hero-actions">
                        <button className="btn btn-primary btn-lg" onClick={openChat}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                            </svg>
                            Start Chat
                        </button>
                        <a href="/login" className="btn btn-secondary btn-lg">Login to Dashboard</a>
                    </div>
                </div>
                <div className="hero-visual">
                    <div className="feature-card">
                        <div className="feature-icon">📋</div>
                        <h3>File a Claim</h3>
                        <p>Auto, Home, or Medical - we've got you covered</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-icon">🔍</div>
                        <h3>Check Status</h3>
                        <p>Real-time updates on your claims</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-icon">💬</div>
                        <h3>Get Answers</h3>
                        <p>Instant help with coverage questions</p>
                    </div>
                </div>
            </section>

            {/* How It Works */}
            <section className="how-it-works">
                <h2 className="section-title">How ClaimBot Works</h2>
                <div className="steps">
                    <div className="step">
                        <div className="step-number">1</div>
                        <h3>Start a Conversation</h3>
                        <p>Click the chat button to connect with our AI assistant instantly.</p>
                    </div>
                    <div className="step">
                        <div className="step-number">2</div>
                        <h3>Describe Your Situation</h3>
                        <p>Tell us what happened and we'll guide you through the process.</p>
                    </div>
                    <div className="step">
                        <div className="step-number">3</div>
                        <h3>Get Results</h3>
                        <p>Receive instant estimates, submit claims, or get connected to a specialist.</p>
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="cta-section">
                <h2>Ready to get started?</h2>
                <p>Our AI assistant is standing by to help 24/7</p>
                <button className="btn btn-primary btn-lg" onClick={openChat}>
                    Chat Now
                </button>
            </section>
        </div>
    )
}

export default HomePage
