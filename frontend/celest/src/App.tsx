import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import LoginPage from './pages/LoginPage'
import QueuePage from './pages/QueuePage'
import CaseDetailPage from './pages/CaseDetailPage'
import LiveChatPage from './pages/LiveChatPage'
import './App.css'

function ProtectedLayout({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, user } = useAuthStore()

    if (!isAuthenticated) {
        return <Navigate to="/login" />
    }

    if (user?.role !== 'celest' && user?.role !== 'admin') {
        return <Navigate to="/login" />
    }

    return (
        <div className="celest-layout">
            <Header />
            <div className="main-container">
                <Sidebar />
                <main className="content">
                    {children}
                </main>
            </div>
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
                        <QueuePage />
                    </ProtectedLayout>
                } />
                <Route path="/case/:caseId" element={
                    <ProtectedLayout>
                        <CaseDetailPage />
                    </ProtectedLayout>
                } />
                <Route path="/live-chat/:caseId" element={
                    <ProtectedLayout>
                        <LiveChatPage />
                    </ProtectedLayout>
                } />
            </Routes>
        </BrowserRouter>
    )
}

export default App
