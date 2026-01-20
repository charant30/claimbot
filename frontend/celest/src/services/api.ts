import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

const API_BASE = '/api'

const api = axios.create({
    baseURL: API_BASE,
})

api.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            useAuthStore.getState().logout()
        }
        return Promise.reject(error)
    }
)

export const authApi = {
    login: async (email: string, password: string) => {
        const response = await api.post('/auth/login', { email, password })
        return response.data
    },
}

export const handoffApi = {
    // Get escalation queue
    getQueue: async () => {
        const response = await api.get('/handoff/queue')
        return response.data
    },

    // Get case details
    getCase: async (caseId: string) => {
        const response = await api.get(`/handoff/case/${caseId}`)
        return response.data
    },

    // Approve case
    approveCase: async (caseId: string, notes?: string) => {
        const response = await api.post(`/handoff/case/${caseId}/approve`, { notes })
        return response.data
    },

    // Deny case
    denyCase: async (caseId: string, reason: string) => {
        const response = await api.post(`/handoff/case/${caseId}/deny`, { reason })
        return response.data
    },

    // Request more info
    requestInfo: async (caseId: string, questions: string[]) => {
        const response = await api.post(`/handoff/case/${caseId}/request-info`, { questions })
        return response.data
    },

    // Take over chat
    takeover: async (caseId: string) => {
        const response = await api.post(`/handoff/case/${caseId}/takeover`)
        return response.data
    },

    // Send message in takeover mode
    sendMessage: async (caseId: string, message: string) => {
        const response = await api.post(`/handoff/case/${caseId}/message`, { message })
        return response.data
    },

    // Get case messages
    getMessages: async (caseId: string) => {
        const response = await api.get(`/handoff/case/${caseId}/messages`)
        return response.data
    },

    // Release case back to AI
    releaseCase: async (caseId: string) => {
        const response = await api.post(`/handoff/case/${caseId}/release`)
        return response.data
    },
}

export default api
