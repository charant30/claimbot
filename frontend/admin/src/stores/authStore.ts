import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '../services/api'

interface User {
    user_id: string
    email: string
    role: string
}

interface AuthState {
    token: string | null
    user: User | null
    isAuthenticated: boolean
    isLoading: boolean
    error: string | null

    login: (email: string, password: string) => Promise<void>
    logout: () => void
    clearError: () => void
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            token: null,
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,

            login: async (email: string, password: string) => {
                set({ isLoading: true, error: null })
                try {
                    const response = await authApi.login(email, password)

                    // Check if admin role
                    if (response.role !== 'admin') {
                        set({
                            error: 'Admin access required',
                            isLoading: false,
                        })
                        return
                    }

                    set({
                        token: response.access_token,
                        user: {
                            user_id: response.user_id,
                            email,
                            role: response.role,
                        },
                        isAuthenticated: true,
                        isLoading: false,
                    })
                } catch (error: any) {
                    set({
                        error: error.response?.data?.detail || 'Login failed',
                        isLoading: false,
                    })
                }
            },

            logout: () => {
                set({
                    token: null,
                    user: null,
                    isAuthenticated: false,
                    error: null,
                })
            },

            clearError: () => set({ error: null }),
        }),
        {
            name: 'claimbot-admin-auth',
            partialize: (state) => ({
                token: state.token,
                user: state.user,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
)
