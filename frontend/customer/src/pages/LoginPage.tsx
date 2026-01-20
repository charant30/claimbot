import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import './LoginPage.css'

function LoginPage() {
    const [searchParams] = useSearchParams()
    const [isSignup, setIsSignup] = useState(searchParams.get('mode') === 'signup')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [name, setName] = useState('')
    const { login, signup, isAuthenticated, isLoading, error, clearError } = useAuthStore()
    const navigate = useNavigate()

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/dashboard')
        }
    }, [isAuthenticated, navigate])

    useEffect(() => {
        clearError()
    }, [isSignup])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        try {
            if (isSignup) {
                await signup(email, password, name)
            } else {
                await login(email, password)
            }
        } catch (err) {
            // Error handled by store
        }
    }

    return (
        <div className="login-page">
            <div className="login-container">
                <div className="login-header">
                    <svg className="login-logo" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                        <path d="M9 12l2 2 4-4" />
                    </svg>
                    <h1>{isSignup ? 'Create Account' : 'Welcome Back'}</h1>
                    <p>{isSignup ? 'Sign up to manage your claims' : 'Login to your ClaimBot account'}</p>
                </div>

                <form className="login-form" onSubmit={handleSubmit}>
                    {isSignup && (
                        <div className="form-group">
                            <label htmlFor="name">Full Name</label>
                            <input
                                id="name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="John Smith"
                                required
                            />
                        </div>
                    )}

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
                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            minLength={6}
                        />
                    </div>

                    {error && <div className="form-error">{error}</div>}

                    <button type="submit" className="btn btn-primary login-submit" disabled={isLoading}>
                        {isLoading ? 'Please wait...' : (isSignup ? 'Create Account' : 'Login')}
                    </button>
                </form>

                <div className="login-footer">
                    <p>
                        {isSignup ? 'Already have an account?' : "Don't have an account?"}
                        <button
                            type="button"
                            className="toggle-mode"
                            onClick={() => setIsSignup(!isSignup)}
                        >
                            {isSignup ? 'Login' : 'Sign Up'}
                        </button>
                    </p>
                </div>

                <div className="demo-credentials">
                    <p><strong>Demo Login:</strong></p>
                    <code>james.smith0@example.com / demo123</code>
                </div>
            </div>
        </div>
    )
}

export default LoginPage
