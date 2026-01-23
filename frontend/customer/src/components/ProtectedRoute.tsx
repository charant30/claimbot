import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

interface ProtectedRouteProps {
    children: React.ReactNode
}

/**
 * ProtectedRoute - Redirects to login if user is not authenticated.
 * Wrap routes that require authentication with this component.
 */
function ProtectedRoute({ children }: ProtectedRouteProps) {
    const { isAuthenticated, isLoading } = useAuthStore()

    // Show loading state while checking auth
    if (isLoading) {
        return (
            <div className="loading-container">
                <p>Loading...</p>
            </div>
        )
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />
    }

    return <>{children}</>
}

export default ProtectedRoute
