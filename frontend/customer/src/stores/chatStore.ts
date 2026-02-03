import { create } from 'zustand'
import { chatApi, claimsApi, documentsApi, policiesApi } from '../services/api'

interface Message {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: Date
    metadata?: Record<string, any>
}

// Conversation flow stages
type FlowStage = 'product_selection' | 'intent_selection' | 'claim_form' | 'document_upload' | 'conversation'

type ClaimFormData = {
    policyNumber: string
    incidentDate: string
    incidentType: string
    location: string
    description: string
    estimatedLoss: string
}

type DocumentItem = {
    doc_id: string
    doc_type: string
    filename: string
    extracted_entities?: Record<string, any>
}

interface ChatState {
    isOpen: boolean
    threadId: string | null
    messages: Message[]
    isLoading: boolean
    policyId: string | null
    claimId: string | null
    claimNumber: string | null
    documents: DocumentItem[]

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
    submitClaimForm: (data: ClaimFormData) => Promise<void>
    uploadDocument: (docType: string, file: File) => Promise<void>
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
    claimId: null,
    claimNumber: null,
    documents: [],
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
                claimId: null,
                claimNumber: null,
                documents: [],
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
                flowStage: intent === 'file_claim' ? 'claim_form' : 'conversation',
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
                flowStage: 'conversation',
            }))
        }
    },

    submitClaimForm: async (data: ClaimFormData) => {
        const { policyId, threadId } = get()
        set({ isLoading: true })

        try {
            let resolvedPolicyId = policyId

            if (!resolvedPolicyId && data.policyNumber) {
                const policy = await policiesApi.lookupPolicy(data.policyNumber)
                resolvedPolicyId = policy.policy_id
                set({ policyId: resolvedPolicyId })
            }

            if (!resolvedPolicyId) {
                throw new Error('Missing policy')
            }

            const claim = await claimsApi.createClaim({
                policy_id: resolvedPolicyId,
                claim_type: 'incident',
                incident_date: data.incidentDate,
                metadata: {
                    incident_type: data.incidentType,
                    location: data.location,
                    description: data.description,
                    estimated_loss: Number(data.estimatedLoss),
                },
            })

            set({
                claimId: claim.claim_id,
                claimNumber: claim.claim_number,
                flowStage: 'document_upload',
            })

            // Add form summary message to chat
            const formSummary = `**Claim Details Submitted:**
• Policy: ${data.policyNumber}
• Incident Date: ${data.incidentDate}
• Incident Type: ${data.incidentType}
• Location: ${data.location}
• Description: ${data.description}
• Estimated Loss: $${data.estimatedLoss}`

            set((state) => ({
                messages: [
                    ...state.messages,
                    {
                        id: `form-summary-${Date.now()}`,
                        role: 'user',
                        content: formSummary,
                        timestamp: new Date(),
                        metadata: { type: 'form_summary', editable: false },
                    },
                ],
            }))

            if (threadId) {
                await chatApi.sendMessage(
                    threadId,
                    `Submitted claim details for policy ${data.policyNumber}.`,
                    {
                        claim_id: claim.claim_id,
                        claim_number: claim.claim_number,
                        claim_form: data,
                    }
                ).then((response) => {
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
                    }))
                })
            } else {
                set((state) => ({
                    messages: [
                        ...state.messages,
                        {
                            id: `bot-${Date.now()}`,
                            role: 'assistant',
                            content: `Thanks! Your claim ${claim.claim_number} is started. Please upload photos of the incident (required) to help us verify and process your claim.`,
                            timestamp: new Date(),
                        },
                    ],
                }))
            }

            set({ isLoading: false })
        } catch (error) {
            console.error('Failed to submit claim form:', error)
            set((state) => ({
                messages: [
                    ...state.messages,
                    {
                        id: `error-${Date.now()}`,
                        role: 'assistant',
                        content: "I couldn't start the claim. Please double-check your policy number and try again.",
                        timestamp: new Date(),
                    },
                ],
                isLoading: false,
            }))
        }
    },

    uploadDocument: async (docType: string, file: File) => {
        const { claimId, threadId, documents } = get()
        if (!claimId) {
            return
        }

        set({ isLoading: true })

        try {
            const response = await documentsApi.upload(claimId, docType, file, threadId || undefined)
            const newDocuments = [...documents, response]

            // Check if required documents (incident_photos) are now uploaded
            const hasRequiredDocs = newDocuments.some(doc => doc.doc_type === 'incident_photos')

            set((state) => ({
                documents: newDocuments,
                // Transition to conversation if required docs are uploaded
                flowStage: hasRequiredDocs ? 'conversation' : state.flowStage,
            }))

            // Add user message showing upload
            set((state) => ({
                messages: [
                    ...state.messages,
                    {
                        id: `upload-${Date.now()}`,
                        role: 'user',
                        content: `Uploaded ${docType.replace(/_/g, ' ')}: ${file.name}`,
                        timestamp: new Date(),
                        metadata: { type: 'document_upload', doc_type: docType },
                    },
                ],
            }))

            if (threadId) {
                const message = `Uploaded ${docType.replace(/_/g, ' ')} document: ${file.name}`
                const chatResponse = await chatApi.sendMessage(threadId, message, {
                    claim_id: claimId,
                    document_id: response.doc_id,
                    doc_type: response.doc_type,
                    extracted_entities: response.extracted_entities,
                })

                set((state) => ({
                    messages: [
                        ...state.messages,
                        {
                            id: chatResponse.message_id,
                            role: 'assistant',
                            content: chatResponse.content,
                            timestamp: new Date(),
                            metadata: chatResponse.metadata,
                        },
                    ],
                }))
            } else {
                set((state) => ({
                    messages: [
                        ...state.messages,
                        {
                            id: `bot-${Date.now()}`,
                            role: 'assistant',
                            content: hasRequiredDocs
                                ? `Document received: ${file.name}. We've verified your incident photos. You can now continue with your claim or upload additional documents.`
                                : `Document received: ${file.name}. Please also upload photos of the incident (required).`,
                            timestamp: new Date(),
                        },
                    ],
                }))
            }

            set({ isLoading: false })
        } catch (error) {
            console.error('Failed to upload document:', error)
            set((state) => ({
                messages: [
                    ...state.messages,
                    {
                        id: `error-${Date.now()}`,
                        role: 'assistant',
                        content: 'Document upload failed. Please try again.',
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
        claimId: null,
        claimNumber: null,
        documents: [],
        flowStage: 'product_selection',
        productLine: null,
        intent: null,
    }),

    setPolicyId: (policyId: string | null) => set({ policyId }),
}))
