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

export const adminApi = {
    // LLM Settings
    getLLMSettings: async () => {
        const response = await api.get('/admin/llm-settings')
        return response.data
    },

    updateLLMSettings: async (settings: {
        llm_provider: string
        bedrock_model?: string
        ollama_model?: string
        ollama_endpoint?: string
    }) => {
        const response = await api.put('/admin/llm-settings', settings)
        return response.data
    },

    // Metrics
    getMetrics: async () => {
        const response = await api.get('/admin/metrics')
        return response.data
    },

    // Audit Logs
    getAuditLogs: async (limit = 100, eventType?: string) => {
        const params = new URLSearchParams({ limit: String(limit) })
        if (eventType) params.append('event_type', eventType)
        const response = await api.get(`/admin/audit-logs?${params}`)
        return response.data
    },

    // Flows
    getFlows: async () => {
        const response = await api.get('/admin/flows')
        return response.data
    },

    // Intents
    getIntents: async () => {
        const response = await api.get('/admin/intents')
        return response.data
    },

    // Transcripts
    getTranscripts: async (limit = 50) => {
        const response = await api.get(`/admin/transcripts?limit=${limit}`)
        return response.data
    },
}

export default api
