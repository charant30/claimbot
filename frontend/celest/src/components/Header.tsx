import { useAuthStore } from '../stores/authStore'
import './Header.css'

function Header() {
    const { user } = useAuthStore()

    return (
        <header className="celest-header">
            <div className="header-left">
                <div className="logo">
                    <span className="logo-icon">⚡</span>
                    <span className="logo-text">Celest</span>
                </div>
                <span className="tagline">Claims Specialist Console</span>
            </div>

            <div className="header-right">
                <div className="status-indicator online">
                    <span className="status-dot"></span>
                    Available
                </div>
                <div className="agent-info">
                    <span className="agent-name">{user?.name}</span>
                    <span className="agent-role">Claims Specialist</span>
                </div>
            </div>
        </header>
    )
}

export default Header
