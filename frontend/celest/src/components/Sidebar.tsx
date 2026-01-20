import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import './Sidebar.css'

function Sidebar() {
    const { logout } = useAuthStore()
    const navigate = useNavigate()

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <aside className="celest-sidebar">
            <nav className="sidebar-nav">
                <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} end>
                    <span className="nav-icon">📥</span>
                    <span className="nav-label">Escalation Queue</span>
                </NavLink>
            </nav>

            <div className="sidebar-stats">
                <h4>Today's Stats</h4>
                <div className="stat-row">
                    <span className="stat-label">Cases Handled</span>
                    <span className="stat-value">12</span>
                </div>
                <div className="stat-row">
                    <span className="stat-label">Avg. Resolution</span>
                    <span className="stat-value">4.2 min</span>
                </div>
                <div className="stat-row">
                    <span className="stat-label">SLA Compliance</span>
                    <span className="stat-value success">98%</span>
                </div>
            </div>

            <button className="logout-btn" onClick={handleLogout}>
                Sign Out
            </button>
        </aside>
    )
}

export default Sidebar
