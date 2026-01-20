import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Sidebar from './components/Sidebar'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import LLMSettingsPage from './pages/LLMSettingsPage'
import FlowsPage from './pages/FlowsPage'
import TranscriptsPage from './pages/TranscriptsPage'
import AuditLogsPage from './pages/AuditLogsPage'
import './App.css'

function ProtectedLayout({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, user } = useAuthStore()

    if (!isAuthenticated) {
        return <Navigate to="/login" />
    }

    if (user?.role !== 'admin') {
        return <Navigate to="/login" />
    }

    return (
        <div className="admin-layout">
            <Sidebar />
            <main className="admin-content">
                {children}
            </main>
        </div>
    )
}

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/" element={
                    <ProtectedLayout>
                        <DashboardPage />
                    </ProtectedLayout>
                } />
                <Route path="/llm-settings" element={
                    <ProtectedLayout>
                        <LLMSettingsPage />
                    </ProtectedLayout>
                } />
                <Route path="/flows" element={
                    <ProtectedLayout>
                        <FlowsPage />
                    </ProtectedLayout>
                } />
                <Route path="/transcripts" element={
                    <ProtectedLayout>
                        <TranscriptsPage />
                    </ProtectedLayout>
                } />
                <Route path="/audit-logs" element={
                    <ProtectedLayout>
                        <AuditLogsPage />
                    </ProtectedLayout>
                } />
            </Routes>
        </BrowserRouter>
    )
}

export default App
