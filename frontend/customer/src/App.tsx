import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Header from './components/Header'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ClaimsPage from './pages/ClaimsPage'
import ChatWidget from './components/ChatWidget'

function App() {
    const { isAuthenticated } = useAuthStore()

    return (
        <BrowserRouter>
            <div className="app">
                <Header />
                <main>
                    <Routes>
                        <Route path="/" element={<HomePage />} />
                        <Route path="/login" element={<LoginPage />} />
                        <Route path="/dashboard" element={<DashboardPage />} />
                        <Route path="/claims" element={<ClaimsPage />} />
                    </Routes>
                </main>
                {/* Chat widget available on all pages */}
                <ChatWidget />
            </div>
        </BrowserRouter>
    )
}

export default App
