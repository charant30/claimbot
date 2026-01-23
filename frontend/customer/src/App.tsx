import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import ProtectedRoute from './components/ProtectedRoute'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ClaimsPage from './pages/ClaimsPage'
import ChatWidget from './components/ChatWidget'

function App() {
    return (
        <BrowserRouter>
            <div className="app">
                <Header />
                <main>
                    <Routes>
                        <Route path="/" element={<HomePage />} />
                        <Route path="/login" element={<LoginPage />} />
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
                {/* Chat widget available on all pages */}
                <ChatWidget />
            </div>
        </BrowserRouter>
    )
}

export default App
