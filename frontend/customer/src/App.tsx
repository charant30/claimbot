import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/Header'
import ProtectedRoute from './components/ProtectedRoute'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ClaimsPage from './pages/ClaimsPage'
import FNOLPage from './pages/FNOLPage'
import ChatWidget from './components/ChatWidget'

function AppContent() {
    const location = useLocation()
    // Don't show header and chat widget on FNOL page (it's full-screen)
    const isFNOLPage = location.pathname === '/fnol'

    return (
        <div className="app">
            {!isFNOLPage && <Header />}
            <main>
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/fnol" element={<FNOLPage />} />
                    <Route
                        path="/dashboard"
                        element={
                            <ProtectedRoute>
                                <DashboardPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/claims"
                        element={
                            <ProtectedRoute>
                                <ClaimsPage />
                            </ProtectedRoute>
                        }
                    />
                </Routes>
            </main>
            {/* Chat widget available on all pages except FNOL */}
            {!isFNOLPage && <ChatWidget />}
        </div>
    )
}

function App() {
    return (
        <BrowserRouter>
            <AppContent />
        </BrowserRouter>
    )
}

export default App
