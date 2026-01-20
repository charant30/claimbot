import { useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import './GuestForm.css'

interface GuestFormProps {
    onSubmit: () => void
}

function GuestForm({ onSubmit }: GuestFormProps) {
    const [name, setName] = useState('')
    const [email, setEmail] = useState('')
    const [policyNumber, setPolicyNumber] = useState('')
    const [error, setError] = useState('')
    const { guestLogin, isLoading } = useAuthStore()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')

        if (!name.trim() || !email.trim()) {
            setError('Please enter your name and email')
            return
        }

        try {
            await guestLogin(name, email)
            onSubmit()
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to start session')
        }
    }

    return (
        <div className="guest-form-container">
            <div className="guest-form-header">
                <h3>Let's get started</h3>
                <p>Please provide your information to continue</p>
            </div>

            <form className="guest-form" onSubmit={handleSubmit}>
                <div className="form-group">
                    <label htmlFor="name">Your Name</label>
                    <input
                        id="name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="John Smith"
                        required
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="email">Email Address</label>
                    <input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="john@example.com"
                        required
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="policyNumber">Policy Number (optional)</label>
                    <input
                        id="policyNumber"
                        type="text"
                        value={policyNumber}
                        onChange={(e) => setPolicyNumber(e.target.value)}
                        placeholder="e.g., AUT-123456"
                    />
                    <small>If you know your policy number, enter it here for faster service</small>
                </div>

                {error && <div className="form-error">{error}</div>}

                <button type="submit" className="btn btn-primary guest-submit" disabled={isLoading}>
                    {isLoading ? 'Starting...' : 'Start Chat'}
                </button>
            </form>

            <div className="guest-form-footer">
                <p>Already have an account? <a href="/login">Login here</a></p>
            </div>
        </div>
    )
}

export default GuestForm
