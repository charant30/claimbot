import { useState, useEffect } from 'react'
import { adminApi } from '../services/api'
import './LLMSettingsPage.css'

interface LLMSettings {
    llm_provider: string
    // OpenAI
    openai_api_key_configured: boolean
    openai_api_key?: string
    openai_model: string
    openai_vision_model: string
    // Bedrock
    bedrock_model: string
    // Ollama
    ollama_model: string
    ollama_vision_model: string
    ollama_endpoint: string
}

function LLMSettingsPage() {
    const [settings, setSettings] = useState<LLMSettings>({
        llm_provider: 'openai',
        openai_api_key_configured: false,
        openai_api_key: '',
        openai_model: 'gpt-4o-mini',
        openai_vision_model: 'gpt-4o-mini',
        bedrock_model: 'anthropic.claude-3-sonnet-20240229-v1:0',
        ollama_model: 'llama3',
        ollama_vision_model: 'llava',
        ollama_endpoint: 'http://localhost:11434',
    })
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const data = await adminApi.getLLMSettings()
                setSettings({ ...settings, ...data, openai_api_key: '' })
            } catch (error) {
                console.error('Failed to fetch LLM settings:', error)
            } finally {
                setLoading(false)
            }
        }
        fetchSettings()
    }, [])

    const handleSave = async () => {
        setSaving(true)
        setMessage(null)
        try {
            // Only send api_key if it was modified
            const payload: any = { ...settings }
            if (!payload.openai_api_key) {
                delete payload.openai_api_key
            }
            await adminApi.updateLLMSettings(payload)
            setMessage({ type: 'success', text: 'Settings saved successfully!' })
            // Clear the API key field after save
            setSettings({ ...settings, openai_api_key: '' })
        } catch (error) {
            setMessage({ type: 'error', text: 'Failed to save settings' })
        } finally {
            setSaving(false)
        }
    }

    if (loading) {
        return <div className="loading">Loading settings...</div>
    }

    return (
        <div className="llm-settings-page">
            <div className="page-header">
                <h1>LLM Settings</h1>
                <p>Configure the AI model provider for chat responses</p>
            </div>

            <div className="settings-card">
                <h2>Provider Selection</h2>
                <p className="settings-description">
                    Choose which LLM provider to use for all AI-powered features.
                    Changes take effect immediately for new conversations.
                </p>

                <div className="provider-toggle">
                    <button
                        className={`provider-btn ${settings.llm_provider === 'openai' ? 'active' : ''}`}
                        onClick={() => setSettings({ ...settings, llm_provider: 'openai' })}
                    >
                        <span className="provider-icon">🤖</span>
                        <span className="provider-name">OpenAI</span>
                        <span className="provider-desc">ChatGPT / GPT-4o</span>
                    </button>
                    <button
                        className={`provider-btn ${settings.llm_provider === 'ollama' ? 'active' : ''}`}
                        onClick={() => setSettings({ ...settings, llm_provider: 'ollama' })}
                    >
                        <span className="provider-icon">🦙</span>
                        <span className="provider-name">Ollama</span>
                        <span className="provider-desc">Local / Self-hosted</span>
                    </button>
                    <button
                        className={`provider-btn ${settings.llm_provider === 'bedrock' ? 'active' : ''}`}
                        onClick={() => setSettings({ ...settings, llm_provider: 'bedrock' })}
                    >
                        <span className="provider-icon">☁️</span>
                        <span className="provider-name">AWS Bedrock</span>
                        <span className="provider-desc">Cloud / Claude 3</span>
                    </button>
                </div>
            </div>

            {settings.llm_provider === 'openai' && (
                <div className="settings-card">
                    <h2>OpenAI Configuration</h2>
                    <div className="form-grid">
                        <div className="form-group">
                            <label>API Key</label>
                            <input
                                type="password"
                                value={settings.openai_api_key}
                                onChange={(e) => setSettings({ ...settings, openai_api_key: e.target.value })}
                                placeholder={settings.openai_api_key_configured ? '••••••••••••••••' : 'sk-...'}
                            />
                            <small>
                                {settings.openai_api_key_configured
                                    ? '✓ API key configured. Enter a new key to update.'
                                    : 'Get your key from platform.openai.com/api-keys'}
                            </small>
                        </div>
                        <div className="form-group">
                            <label>Chat Model</label>
                            <select
                                value={settings.openai_model}
                                onChange={(e) => setSettings({ ...settings, openai_model: e.target.value })}
                            >
                                <option value="gpt-4o-mini">GPT-4o Mini (Recommended)</option>
                                <option value="gpt-4o">GPT-4o</option>
                                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Vision Model (OCR)</label>
                            <select
                                value={settings.openai_vision_model}
                                onChange={(e) => setSettings({ ...settings, openai_vision_model: e.target.value })}
                            >
                                <option value="gpt-4o-mini">GPT-4o Mini (Recommended)</option>
                                <option value="gpt-4o">GPT-4o</option>
                                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                            </select>
                            <small>Used for document/image analysis</small>
                        </div>
                    </div>
                </div>
            )}

            {settings.llm_provider === 'ollama' && (
                <div className="settings-card">
                    <h2>Ollama Configuration</h2>
                    <div className="form-grid">
                        <div className="form-group">
                            <label>Model Name</label>
                            <input
                                type="text"
                                value={settings.ollama_model}
                                onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                                placeholder="llama3"
                            />
                            <small>Common models: llama3, mistral, codellama, gemma</small>
                        </div>
                        <div className="form-group">
                            <label>Vision Model</label>
                            <input
                                type="text"
                                value={settings.ollama_vision_model}
                                onChange={(e) => setSettings({ ...settings, ollama_vision_model: e.target.value })}
                                placeholder="llava"
                            />
                            <small>Used for document/image analysis</small>
                        </div>
                        <div className="form-group">
                            <label>Endpoint URL</label>
                            <input
                                type="text"
                                value={settings.ollama_endpoint}
                                onChange={(e) => setSettings({ ...settings, ollama_endpoint: e.target.value })}
                                placeholder="http://localhost:11434"
                            />
                            <small>Default: http://localhost:11434</small>
                        </div>
                    </div>
                </div>
            )}

            {settings.llm_provider === 'bedrock' && (
                <div className="settings-card">
                    <h2>AWS Bedrock Configuration</h2>
                    <div className="form-group">
                        <label>Model ID</label>
                        <select
                            value={settings.bedrock_model}
                            onChange={(e) => setSettings({ ...settings, bedrock_model: e.target.value })}
                        >
                            <option value="anthropic.claude-3-sonnet-20240229-v1:0">Claude 3 Sonnet</option>
                            <option value="anthropic.claude-3-haiku-20240307-v1:0">Claude 3 Haiku</option>
                            <option value="anthropic.claude-instant-v1">Claude Instant</option>
                        </select>
                        <small>AWS credentials must be configured in environment variables</small>
                    </div>
                </div>
            )}

            {message && (
                <div className={`message ${message.type}`}>
                    {message.text}
                </div>
            )}

            <div className="actions">
                <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>
        </div>
    )
}

export default LLMSettingsPage

