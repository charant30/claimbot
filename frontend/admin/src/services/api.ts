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

    updateFlowSettings: async (settings: Record<string, unknown>) => {
        const response = await api.put('/admin/flows/settings', settings)
        return response.data
    },

    createFlowRule: async (rule: {
        name: string
        description?: string
        conditions: Record<string, unknown>
        action: Record<string, unknown>
        priority?: number
    }) => {
        const response = await api.post('/admin/flows/rules', rule)
        return response.data
    },

    updateFlowRule: async (ruleId: string, rule: Record<string, unknown>) => {
        const response = await api.put(`/admin/flows/rules/${ruleId}`, rule)
        return response.data
    },

    deleteFlowRule: async (ruleId: string) => {
        const response = await api.delete(`/admin/flows/rules/${ruleId}`)
        return response.data
    },

    // Intents
    getIntents: async () => {
        const response = await api.get('/admin/intents')
        return response.data
    },

    createIntent: async (intent: {
        name: string
        display_name: string
        description?: string
        applicable_products?: string[]
        trigger_phrases?: string[]
        required_fields?: string[]
        flow_config?: Record<string, unknown>
        icon?: string
    }) => {
        const response = await api.post('/admin/intents', intent)
        return response.data
    },

    updateIntent: async (intentId: string, intent: Record<string, unknown>) => {
        const response = await api.put(`/admin/intents/${intentId}`, intent)
        return response.data
    },

    deleteIntent: async (intentId: string) => {
        const response = await api.delete(`/admin/intents/${intentId}`)
        return response.data
    },

    // Document Flows
    getDocumentFlows: async (productLine?: string) => {
        const params = productLine ? `?product_line=${productLine}` : ''
        const response = await api.get(`/admin/document-flows${params}`)
        return response.data
    },

    createDocumentFlow: async (flow: {
        product_line: string
        incident_type?: string
        document_sequence: string[]
        conditional_rules?: Record<string, unknown>
        field_requirements?: Record<string, string[]>
    }) => {
        const response = await api.post('/admin/document-flows', flow)
        return response.data
    },

    updateDocumentFlow: async (configId: string, flow: Record<string, unknown>) => {
        const response = await api.put(`/admin/document-flows/${configId}`, flow)
        return response.data
    },

    deleteDocumentFlow: async (configId: string) => {
        const response = await api.delete(`/admin/document-flows/${configId}`)
        return response.data
    },

    // Transcripts
    getTranscripts: async (limit = 50) => {
        const response = await api.get(`/admin/transcripts?limit=${limit}`)
        return response.data
    },

    getTranscriptDetail: async (threadId: string) => {
        const response = await api.get(`/admin/transcripts/${threadId}`)
        return response.data
    },
}

export default api
