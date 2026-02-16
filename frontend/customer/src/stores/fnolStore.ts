import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { fnolApi, FNOLSessionResponse, FNOLMessageResponse, FNOLSummaryResponse } from '../services/api'

// FNOL State machine states
export const FNOL_STATES = [
    'SAFETY_CHECK',
    'IDENTITY_MATCH',
    'INCIDENT_CORE',
    'LOSS_MODULE',
    'VEHICLE_DRIVER',
    'THIRD_PARTIES',
    'INJURIES',
    'DAMAGE_EVIDENCE',
    'TRIAGE',
    'CLAIM_CREATE',
    'NEXT_STEPS',
    'HANDOFF_ESCALATION',
] as const

export type FNOLStateName = typeof FNOL_STATES[number]

// State labels for display
export const STATE_LABELS: Record<FNOLStateName, string> = {
    SAFETY_CHECK: 'Safety Check',
    IDENTITY_MATCH: 'Identity',
    INCIDENT_CORE: 'Incident Details',
    LOSS_MODULE: 'Loss Type',
    VEHICLE_DRIVER: 'Vehicle & Driver',
    THIRD_PARTIES: 'Other Parties',
    INJURIES: 'Injuries',
    DAMAGE_EVIDENCE: 'Damage & Evidence',
    TRIAGE: 'Review',
    CLAIM_CREATE: 'Submit',
    NEXT_STEPS: 'Next Steps',
    HANDOFF_ESCALATION: 'Agent Handoff',
}

export interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: string
}

export interface InputOption {
    value: string
    label: string
}

/** Inactivity timeout before prompting to end session (ms) */
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000 // 15 minutes

interface FNOLState {
    // Session
    threadId: string | null
    claimDraftId: string | null
    isSessionActive: boolean
    /** When the user explicitly ended the session (so we don't resume on next open) */
    sessionEndedAt: number | null

    // State machine
    currentState: FNOLStateName
    completedStates: FNOLStateName[]
    progressPercent: number

    // Conversation
    messages: Message[]
    currentMessage: string
    isLoading: boolean
    error: string | null

    // Current question
    pendingQuestion: string | null
    inputType: string
    inputOptions: InputOption[]
    validationErrors: string[]

    // Completion
    isComplete: boolean
    shouldEscalate: boolean
    escalationReason: string | null

    // Summary
    summary: FNOLSummaryResponse | null

    // UI state
    showSummary: boolean

    // Actions
    startSession: (policyId?: string) => Promise<void>
    sendMessage: (message: string) => Promise<void>
    uploadDocument: (file: File, evidenceType?: string) => Promise<void>
    resumeSession: (threadId: string) => Promise<void>
    endSession: () => Promise<void>
    refreshMessages: () => Promise<void>
    loadSummary: () => Promise<void>
    resetSession: () => void
    /** Call when user is active (e.g. sent message) to reset inactivity timer */
    touchActivity: () => void
    setCurrentMessage: (message: string) => void
    toggleSummary: () => void
    clearError: () => void
}

const initialState = {
    threadId: null,
    claimDraftId: null,
    isSessionActive: false,
    sessionEndedAt: null as number | null,
    currentState: 'SAFETY_CHECK' as FNOLStateName,
    completedStates: [] as FNOLStateName[],
    progressPercent: 0,
    messages: [] as Message[],
    currentMessage: '',
    isLoading: false,
    error: null,
    pendingQuestion: null,
    inputType: 'text',
    inputOptions: [] as InputOption[],
    validationErrors: [] as string[],
    isComplete: false,
    shouldEscalate: false,
    escalationReason: null,
    summary: null,
    showSummary: false,
}

export const useFNOLStore = create<FNOLState>()(
    persist(
        (set, get) => ({
            ...initialState,

            startSession: async (policyId?: string) => {
                set({ isLoading: true, error: null, sessionEndedAt: null })
                try {
                    const response = await fnolApi.createSession(policyId)
                    handleSessionResponse(set, response)
                } catch (error: any) {
                    set({
                        error: error.response?.data?.detail || 'Failed to start session',
                        isLoading: false,
                    })
                    throw error
                }
            },

            sendMessage: async (message: string) => {
                const { threadId, messages, shouldEscalate } = get()
                if (!threadId) {
                    set({ error: 'No active session' })
                    return
                }

                // Add user message to UI immediately
                const userMessage: Message = {
                    id: `user-${Date.now()}`,
                    role: 'user',
                    content: message,
                    timestamp: new Date().toISOString(),
                }

                set({
                    messages: [...messages, userMessage],
                    currentMessage: '',
                    isLoading: true,
                    error: null,
                    validationErrors: [],
                })

                // During escalation, bypass state machine and send directly
                if (shouldEscalate) {
                    try {
                        await fnolApi.sendEscalationMessage(threadId, message)
                        set({ isLoading: false })
                    } catch (error: any) {
                        set({
                            error: error.response?.data?.detail || 'Failed to send message',
                            isLoading: false,
                        })
                    }
                    return
                }

                try {
                    const response = await fnolApi.sendMessage(threadId, message)
                    handleMessageResponse(set, get, response)
                } catch (error: any) {
                    set({
                        error: error.response?.data?.detail || 'Failed to send message',
                        isLoading: false,
                    })
                }
            },

            uploadDocument: async (file: File, evidenceType: string = 'photo') => {
                const { threadId, messages } = get()
                if (!threadId) {
                    set({ error: 'No active session' })
                    return
                }

                set({ isLoading: true, error: null })

                try {
                    await fnolApi.uploadDocument(threadId, file, evidenceType)

                    // Add system message about upload
                    const uploadMessage: Message = {
                        id: `system-${Date.now()}`,
                        role: 'assistant',
                        content: `Photo uploaded successfully.`,
                        timestamp: new Date().toISOString(),
                    }

                    set({
                        messages: [...messages, uploadMessage],
                        isLoading: false,
                    })
                } catch (error: any) {
                    set({
                        error: error.response?.data?.detail || 'Failed to upload document',
                        isLoading: false,
                    })
                }
            },

            resumeSession: async (threadId: string) => {
                set({ isLoading: true, error: null })
                try {
                    const response = await fnolApi.resumeSession(threadId)
                    handleSessionResponse(set, response)
                } catch (error: any) {
                    // Session ended or expired
                    set({
                        ...initialState,
                        sessionEndedAt: null,
                        error: error.response?.data?.detail || 'Session expired. Please start a new claim.',
                        isLoading: false,
                    })
                    throw error
                }
            },

            endSession: async () => {
                const { threadId } = get()
                if (!threadId) {
                    set({ ...initialState, sessionEndedAt: Date.now() })
                    return
                }
                try {
                    await fnolApi.endSession(threadId)
                } finally {
                    set({ ...initialState, sessionEndedAt: Date.now() })
                }
            },

            touchActivity: () => {
                set({}) // no-op; inactivity timer is reset in the widget via effect
            },

            refreshMessages: async () => {
                const { threadId } = get()
                if (!threadId) return

                try {
                    const history = await fnolApi.getMessages(threadId)
                    const messages: Message[] = history.map((h, i) => ({
                        id: h.message_id || `msg-${i}-${h.timestamp || ''}`,
                        role: (h.role === 'agent' ? 'assistant' : h.role) as 'user' | 'assistant',
                        content: h.role === 'agent'
                            ? `**Claims Specialist:** ${h.content}`
                            : h.content,
                        timestamp: h.timestamp
                    }))

                    const validMessages = messages.filter(m => m.content && m.content.trim() !== "")

                    set((state) => {
                        const prev = state.messages
                        if (prev.length > 0 && validMessages.length >= prev.length) {
                            const sameLength = validMessages.length === prev.length
                            const sameContent = sameLength && validMessages.every((m, i) =>
                                prev[i]?.id === m.id && prev[i]?.content === m.content
                            )
                            if (sameContent) return state
                        }
                        return { ...state, messages: validMessages }
                    })
                } catch (error) {
                    console.error('Failed to refresh messages', error)
                }
            },

            loadSummary: async () => {
                const { threadId } = get()
                if (!threadId) return

                try {
                    const summary = await fnolApi.getSummary(threadId)
                    set({ summary, showSummary: true })
                } catch (error: any) {
                    set({ error: 'Failed to load summary' })
                }
            },

            resetSession: () => {
                set(initialState)
            },

            setCurrentMessage: (message: string) => {
                set({ currentMessage: message })
            },

            toggleSummary: () => {
                set((state) => ({ showSummary: !state.showSummary }))
            },

            clearError: () => {
                set({ error: null })
            },
        }),
        {
            name: 'fnol-session',
            partialize: (state) => ({
                threadId: state.threadId,
                claimDraftId: state.claimDraftId,
                currentState: state.currentState,
                completedStates: state.completedStates,
                progressPercent: state.progressPercent,
                isSessionActive: state.isSessionActive,
                sessionEndedAt: state.sessionEndedAt,
                messages: state.messages.slice(-100),
            }),
        }
    )
)

// Helper functions
function handleSessionResponse(
    set: (state: Partial<FNOLState>) => void,
    response: FNOLSessionResponse
) {
    const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
    }

    set({
        threadId: response.thread_id,
        claimDraftId: response.claim_draft_id,
        isSessionActive: true,
        currentState: response.current_state as FNOLStateName,
        completedStates: (response.progress?.completed || []) as FNOLStateName[],
        progressPercent: response.progress?.percent || 0,
        messages: [assistantMessage],
        inputType: response.input_type || 'text',
        inputOptions: response.options || [],
        isLoading: false,
    })
}

function handleMessageResponse(
    set: (state: Partial<FNOLState>) => void,
    get: () => FNOLState,
    response: FNOLMessageResponse
) {
    const { messages } = get()

    // Add assistant response
    const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
    }

    set({
        messages: [...messages, assistantMessage],
        currentState: response.current_state as FNOLStateName,
        completedStates: (response.progress?.completed || []) as FNOLStateName[],
        progressPercent: response.progress?.percent || 0,
        inputType: response.input_type || 'text',
        inputOptions: response.options || [],
        validationErrors: response.validation_errors || [],
        isComplete: response.is_complete,
        shouldEscalate: response.should_escalate,
        escalationReason: response.escalation_reason || null,
        isLoading: false,
    })
}
