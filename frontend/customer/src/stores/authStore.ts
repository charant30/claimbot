import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '../services/api'

interface User {
    user_id: string
    email: string
    name: string
    role: string
}

interface AuthState {
    token: string | null
    user: User | null
    isAuthenticated: boolean
    isLoading: boolean
    error: string | null

    login: (email: string, password: string) => Promise<void>
    signup: (email: string, password: string, name: string) => Promise<void>
    guestLogin: (name: string, email: string) => Promise<void>
    logout: () => void
    clearError: () => void
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            token: null,
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,

            login: async (email: string, password: string) => {
                set({ isLoading: true, error: null })
                try {
                    const response = await authApi.login(email, password)
                    set({
                        token: response.access_token,
                        user: {
                            user_id: response.user_id,
                            email,
                            name: '', // Will be fetched from /me
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
                    throw error
                }
            },

            signup: async (email: string, password: string, name: string) => {
                set({ isLoading: true, error: null })
                try {
                    const response = await authApi.signup(email, password, name)
                    set({
                        token: response.access_token,
                        user: {
                            user_id: response.user_id,
                            email,
                            name,
                            role: response.role,
                        },
                        isAuthenticated: true,
                        isLoading: false,
                    })
                } catch (error: any) {
                    set({
                        error: error.response?.data?.detail || 'Signup failed',
                        isLoading: false,
                    })
                    throw error
                }
            },

            guestLogin: async (name: string, email: string) => {
                set({ isLoading: true, error: null })
                try {
                    const response = await authApi.guestSession(name, email)
                    set({
                        token: response.access_token,
                        user: {
                            user_id: response.user_id,
                            email,
                            name,
                            role: 'customer',
                        },
                        isAuthenticated: true,
                        isLoading: false,
                    })
                } catch (error: any) {
                    set({
                        error: error.response?.data?.detail || 'Guest login failed',
                        isLoading: false,
                    })
                    throw error
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
            name: 'claimbot-auth',
            partialize: (state) => ({
                token: state.token,
                user: state.user,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
)
