import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

const API_BASE = '/api'

// Create axios instance with auth interceptor
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

// Auth API
export const authApi = {
    login: async (email: string, password: string) => {
        const response = await api.post('/auth/login', { email, password })
        return response.data
    },

    signup: async (email: string, password: string, name: string) => {
        const response = await api.post('/auth/signup', { email, password, name })
        return response.data
    },

    guestSession: async (name: string, email: string, policyNumber?: string) => {
        let url = `/auth/guest-session?name=${encodeURIComponent(name)}&email=${encodeURIComponent(email)}`
        if (policyNumber) {
            url += `&policy_number=${encodeURIComponent(policyNumber)}`
        }
        const response = await api.post(url)
        return response.data
    },

    logout: async () => {
        await api.post('/auth/logout')
    },
}

// Policies API
export const policiesApi = {
    getMyPolicies: async () => {
        const response = await api.get('/policies/me')
        return response.data
    },

    getPolicy: async (policyId: string) => {
        const response = await api.get(`/policies/${policyId}`)
        return response.data
    },

    lookupPolicy: async (policyNumber: string) => {
        const response = await api.post('/policies/lookup', { policy_number: policyNumber })
        return response.data
    },
}

// Claims API
export const claimsApi = {
    getMyClaims: async () => {
        const response = await api.get('/claims/')
        return response.data
    },

    getClaim: async (claimId: string) => {
        const response = await api.get(`/claims/${claimId}`)
        return response.data
    },

    createClaim: async (data: {
        policy_id: string
        claim_type: string
        incident_date: string
        metadata?: Record<string, any>
    }) => {
        const response = await api.post('/claims/', data)
        return response.data
    },
}

// Chat API
export const chatApi = {
    createSession: async (policyId?: string, productLine?: string) => {
        const response = await api.post('/chat/session', {
            policy_id: policyId,
            product_line: productLine,
        })
        return response.data
    },

    sendMessage: async (threadId: string, message: string, metadata?: Record<string, any>) => {
        const response = await api.post('/chat/message', {
            thread_id: threadId,
            message,
            metadata: metadata || {},
        })
        return response.data
    },

    getMessages: async (threadId: string) => {
        const response = await api.get(`/chat/session/${threadId}/messages`)
        return response.data
    },
}

// Documents API
export const documentsApi = {
    upload: async (claimId: string, docType: string, file: File, threadId?: string) => {
        const formData = new FormData()
        formData.append('claim_id', claimId)
        formData.append('doc_type', docType)
        formData.append('file', file)
        if (threadId) {
            formData.append('thread_id', threadId)
        }

        const response = await api.post('/documents/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        return response.data
    },

    getClaimDocuments: async (claimId: string) => {
        const response = await api.get(`/documents/claim/${claimId}`)
        return response.data
    },
}

// FNOL API
export interface FNOLSessionResponse {
    thread_id: string
    claim_draft_id: string
    current_state: string
    message: string
    needs_input: boolean
    input_type: string
    options: Array<{ value: string; label: string }>
    progress: {
        current: string
        completed: string[]
        percent: number
    }
    ui_hints: Record<string, any>
}

export interface FNOLMessageResponse extends FNOLSessionResponse {
    validation_errors: string[]
    is_complete: boolean
    should_escalate: boolean
    escalation_reason?: string
}

export interface FNOLStateResponse {
    thread_id: string
    claim_draft_id: string
    status: string
    current_state: string
    progress_percent: number
    completed_states: string[]
    collected_data: Record<string, any>
}

export interface FNOLSummaryResponse {
    thread_id: string
    claim_draft_id: string
    summary: Record<string, any>
    can_submit: boolean
    validation_errors: string[]
}

export const fnolApi = {
    createSession: async (policyId?: string): Promise<FNOLSessionResponse> => {
        const response = await api.post('/fnol/session', {
            policy_id: policyId,
        })
        return response.data
    },

    sendMessage: async (
        threadId: string,
        message: string,
        metadata?: Record<string, any>
    ): Promise<FNOLMessageResponse> => {
        const response = await api.post('/fnol/message', {
            thread_id: threadId,
            message,
            metadata: metadata || {},
        })
        return response.data
    },

    getState: async (threadId: string): Promise<FNOLStateResponse> => {
        const response = await api.get(`/fnol/session/${threadId}/state`)
        return response.data
    },

    getSummary: async (threadId: string): Promise<FNOLSummaryResponse> => {
        const response = await api.get(`/fnol/session/${threadId}/summary`)
        return response.data
    },

    uploadDocument: async (
        threadId: string,
        file: File,
        evidenceType: string = 'photo'
    ): Promise<{ evidence_id: string; evidence_type: string; upload_status: string }> => {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('evidence_type', evidenceType)

        const response = await api.post(`/fnol/session/${threadId}/document`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        return response.data
    },

    resumeSession: async (threadId: string): Promise<FNOLSessionResponse> => {
        const response = await api.post(`/fnol/session/${threadId}/resume`)
        return response.data
    },
}

export default api
