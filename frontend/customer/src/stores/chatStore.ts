import { create } from 'zustand'
import { chatApi } from '../services/api'

interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
    metadata?: Record<string, any>
}

interface ChatState {
    isOpen: boolean
    threadId: string | null
    messages: Message[]
    isLoading: boolean
    policyId: string | null

    toggleChat: () => void
    openChat: () => void
    closeChat: () => void
    startSession: (policyId?: string) => Promise<void>
    sendMessage: (content: string) => Promise<void>
    clearChat: () => void
    setPolicyId: (policyId: string | null) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
    isOpen: false,
    threadId: null,
    messages: [],
    isLoading: false,
    policyId: null,

    toggleChat: () => set((state) => ({ isOpen: !state.isOpen })),
    openChat: () => set({ isOpen: true }),
    closeChat: () => set({ isOpen: false }),

    startSession: async (policyId?: string) => {
        try {
            const response = await chatApi.createSession(policyId)
            set({
                threadId: response.thread_id,
                messages: [{
                    id: 'welcome',
                    role: 'assistant',
                    content: "Hello! I'm your ClaimBot assistant. How can I help you today?\n\n• File a new claim\n• Check claim status\n• Ask about your coverage\n• Billing questions",
                    timestamp: new Date(),
                }],
                policyId: policyId || null,
            })
        } catch (error) {
            console.error('Failed to start chat session:', error)
        }
    },

    sendMessage: async (content: string) => {
        const { threadId, messages } = get()

        if (!threadId) {
            await get().startSession()
        }

        const currentThreadId = get().threadId
        if (!currentThreadId) return

        // Add user message immediately
        const userMessage: Message = {
            id: `user-${Date.now()}`,
            role: 'user',
            content,
            timestamp: new Date(),
        }

        set({
            messages: [...messages, userMessage],
            isLoading: true,
        })

        try {
            const response = await chatApi.sendMessage(currentThreadId, content)

            const assistantMessage: Message = {
                id: response.message_id,
                role: 'assistant',
                content: response.content,
                timestamp: new Date(),
                metadata: response.metadata,
            }

            set((state) => ({
                messages: [...state.messages, assistantMessage],
                isLoading: false,
            }))
        } catch (error) {
            console.error('Failed to send message:', error)

            const errorMessage: Message = {
                id: `error-${Date.now()}`,
                role: 'assistant',
                content: "I'm sorry, I encountered an error. Please try again.",
                timestamp: new Date(),
            }

            set((state) => ({
                messages: [...state.messages, errorMessage],
                isLoading: false,
            }))
        }
    },

    clearChat: () => set({
        threadId: null,
        messages: [],
        policyId: null,
    }),

    setPolicyId: (policyId: string | null) => set({ policyId }),
}))
