import { create } from 'zustand'
import { chatApi } from '../services/api'

interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
    metadata?: Record<string, any>
}

// Conversation flow stages
type FlowStage = 'product_selection' | 'intent_selection' | 'conversation'

interface ChatState {
    isOpen: boolean
    threadId: string | null
    messages: Message[]
    isLoading: boolean
    policyId: string | null

    // Guided flow state
    flowStage: FlowStage
    productLine: string | null
    intent: string | null

    toggleChat: () => void
    openChat: () => void
    closeChat: () => void
    startSession: (policyId?: string) => Promise<void>
    sendMessage: (content: string, metadata?: Record<string, any>) => Promise<void>
    selectProduct: (product: string) => void
    selectIntent: (intent: string) => Promise<void>
    clearChat: () => void
    setPolicyId: (policyId: string | null) => void
}

const PRODUCT_OPTIONS = [
    { id: 'auto', icon: '🚗', label: 'Auto Insurance' },
    { id: 'home', icon: '🏠', label: 'Home Insurance' },
    { id: 'medical', icon: '🏥', label: 'Medical Insurance' },
]

const INTENT_OPTIONS = [
    { id: 'file_claim', icon: '📝', label: 'File a New Claim' },
    { id: 'check_status', icon: '🔍', label: 'Check Claim Status' },
    { id: 'coverage_question', icon: '❓', label: 'Coverage Questions' },
    { id: 'billing', icon: '💵', label: 'Billing Inquiry' },
]

export { PRODUCT_OPTIONS, INTENT_OPTIONS }

export const useChatStore = create<ChatState>((set, get) => ({
    isOpen: false,
    threadId: null,
    messages: [],
    isLoading: false,
    policyId: null,
    flowStage: 'product_selection',
    productLine: null,
    intent: null,

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
                    content: "Hello! I'm ClaimBot, your insurance assistant. What type of insurance can I help you with today?",
                    timestamp: new Date(),
                }],
                policyId: policyId || null,
                flowStage: 'product_selection',
                productLine: null,
                intent: null,
            })
        } catch (error) {
            console.error('Failed to start chat session:', error)
        }
    },

    selectProduct: (product: string) => {
        const productLabel = PRODUCT_OPTIONS.find(p => p.id === product)?.label || product

        // Add user's selection as a message
        set((state) => ({
            productLine: product,
            flowStage: 'intent_selection',
            messages: [
                ...state.messages,
                {
                    id: `user-${Date.now()}`,
                    role: 'user',
                    content: productLabel,
                    timestamp: new Date(),
                },
                {
                    id: `bot-${Date.now()}`,
                    role: 'assistant',
                    content: `Great! How can I help you with your ${productLabel.toLowerCase()}?`,
                    timestamp: new Date(),
                },
            ],
        }))
    },

    selectIntent: async (intent: string) => {
        const { productLine, threadId } = get()
        const intentLabel = INTENT_OPTIONS.find(i => i.id === intent)?.label || intent

        // Add user's selection as a message
        set((state) => ({
            intent,
            flowStage: 'conversation',
            messages: [
                ...state.messages,
                {
                    id: `user-${Date.now()}`,
                    role: 'user',
                    content: intentLabel,
                    timestamp: new Date(),
                },
            ],
            isLoading: true,
        }))

        // Send the selection to backend with metadata
        try {
            if (!threadId) return

            const response = await chatApi.sendMessage(
                threadId,
                `I want to ${intentLabel.toLowerCase()} for my ${productLine} insurance.`,
                { product_line: productLine, intent }
            )

            set((state) => ({
                messages: [
                    ...state.messages,
                    {
                        id: response.message_id,
                        role: 'assistant',
                        content: response.content,
                        timestamp: new Date(),
                        metadata: response.metadata,
                    },
                ],
                isLoading: false,
            }))
        } catch (error) {
            console.error('Failed to send intent:', error)
            set((state) => ({
                messages: [
                    ...state.messages,
                    {
                        id: `error-${Date.now()}`,
                        role: 'assistant',
                        content: "I'm sorry, I encountered an error. Please try again.",
                        timestamp: new Date(),
                    },
                ],
                isLoading: false,
            }))
        }
    },

    sendMessage: async (content: string, metadata?: Record<string, any>) => {
        const { threadId, messages, productLine, intent } = get()

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
            const response = await chatApi.sendMessage(
                currentThreadId,
                content,
                { ...metadata, product_line: productLine, intent }
            )

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
        flowStage: 'product_selection',
        productLine: null,
        intent: null,
    }),

    setPolicyId: (policyId: string | null) => set({ policyId }),
}))
