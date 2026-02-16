import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import './Sidebar.css'

const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/transcripts', label: 'Transcripts', icon: '📝' },
    { path: '/llm-settings', label: 'LLM Settings', icon: '🤖' },
    { path: '/flows', label: 'Flows & Intents', icon: '🔀' },
]

function Sidebar() {
    const { user, logout } = useAuthStore()
    const navigate = useNavigate()

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="sidebar-logo">
                    <span className="logo-icon">🛡️</span>
                    <span className="logo-text">ClaimBot Admin</span>
                </div>
            </div>

            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                        end={item.path === '/'}
                    >
                        <span className="nav-icon">{item.icon}</span>
                        <span className="nav-label">{item.label}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="sidebar-footer">
                <div className="user-info">
                    <div className="user-avatar">👤</div>
                    <div className="user-details">
                        <span className="user-email">{user?.email}</span>
                        <span className="user-role">Administrator</span>
                    </div>
                </div>
                <button className="logout-btn" onClick={handleLogout}>
                    Logout
                </button>
            </div>
        </aside>
    )
}

export default Sidebar
