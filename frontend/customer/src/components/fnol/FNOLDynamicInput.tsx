import React, { useState, useRef } from 'react'
import { useFNOLStore } from '../../stores/fnolStore'

interface FNOLDynamicInputProps {
    onSubmit: (value: string) => void
    isLoading: boolean
}

export const FNOLDynamicInput: React.FC<FNOLDynamicInputProps> = ({
    onSubmit,
    isLoading,
}) => {
    const { inputType, inputOptions, currentMessage, setCurrentMessage, validationErrors } = useFNOLStore()
    const [selectedOptions, setSelectedOptions] = useState<string[]>([])
    const fileInputRef = useRef<HTMLInputElement>(null)

    const handleTextSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (currentMessage.trim() && !isLoading) {
            onSubmit(currentMessage.trim())
        }
    }

    const handleOptionSelect = (value: string) => {
        if (!isLoading) {
            onSubmit(value)
        }
    }

    const handleMultiSelect = (value: string) => {
        setSelectedOptions((prev) =>
            prev.includes(value)
                ? prev.filter((v) => v !== value)
                : [...prev, value]
        )
    }

    const handleMultiSubmit = () => {
        if (selectedOptions.length > 0 && !isLoading) {
            onSubmit(selectedOptions.join(', '))
            setSelectedOptions([])
        }
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            // Will be handled by parent component
            onSubmit(`[Photo: ${file.name}]`)
        }
    }

    const renderInput = () => {
        switch (inputType) {
            case 'yesno':
                return (
                    <div className="option-buttons" role="group" aria-label="Yes or no selection">
                        {inputOptions.map((option) => (
                            <button
                                key={option.value}
                                className={`option-button ${option.value === 'yes' ? 'primary' : 'secondary'}`}
                                onClick={() => handleOptionSelect(option.value)}
                                disabled={isLoading}
                                aria-label={option.label}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                )

            case 'select':
                return (
                    <div className="option-buttons select-options" role="group" aria-label="Select an option">
                        {inputOptions.map((option) => (
                            <button
                                key={option.value}
                                className="option-button"
                                onClick={() => handleOptionSelect(option.value)}
                                disabled={isLoading}
                                aria-label={`Select ${option.label}`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                )

            case 'multiselect':
                return (
                    <div className="multiselect-container">
                        <fieldset className="checkbox-group" role="group" aria-label="Select all that apply">
                            {inputOptions.map((option) => (
                                <label key={option.value} className="checkbox-option">
                                    <input
                                        type="checkbox"
                                        checked={selectedOptions.includes(option.value)}
                                        onChange={() => handleMultiSelect(option.value)}
                                        disabled={isLoading}
                                        aria-label={option.label}
                                    />
                                    <span>{option.label}</span>
                                </label>
                            ))}
                        </fieldset>
                        <button
                            className="submit-button"
                            onClick={handleMultiSubmit}
                            disabled={selectedOptions.length === 0 || isLoading}
                            aria-label="Continue with selected options"
                        >
                            Continue
                        </button>
                    </div>
                )

            case 'date':
                return (
                    <form onSubmit={handleTextSubmit} className="text-input-form" aria-label="Date selection">
                        <input
                            type="date"
                            value={currentMessage}
                            onChange={(e) => setCurrentMessage(e.target.value)}
                            disabled={isLoading}
                            className="date-input"
                            aria-label="Select date"
                        />
                        <button type="submit" disabled={!currentMessage || isLoading} className="submit-button" aria-label="Continue with selected date">
                            Continue
                        </button>
                    </form>
                )

            case 'time':
                return (
                    <form onSubmit={handleTextSubmit} className="text-input-form" aria-label="Time selection">
                        <input
                            type="time"
                            value={currentMessage}
                            onChange={(e) => setCurrentMessage(e.target.value)}
                            disabled={isLoading}
                            className="time-input"
                            aria-label="Select time"
                        />
                        <button type="submit" disabled={!currentMessage || isLoading} className="submit-button" aria-label="Continue with selected time">
                            Continue
                        </button>
                    </form>
                )

            case 'photo':
                return (
                    <div className="photo-input" role="group" aria-label="Photo upload">
                        <input
                            type="file"
                            ref={fileInputRef}
                            accept="image/*"
                            capture="environment"
                            onChange={handleFileSelect}
                            className="hidden"
                            aria-label="Select photo file"
                        />
                        <button
                            className="photo-button"
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isLoading}
                            aria-label="Take or upload a photo of the damage"
                        >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                <circle cx="8.5" cy="8.5" r="1.5" />
                                <polyline points="21 15 16 10 5 21" />
                            </svg>
                            Take or Upload Photo
                        </button>
                        <button
                            className="skip-button"
                            onClick={() => onSubmit('skip')}
                            disabled={isLoading}
                            aria-label="Skip photo upload"
                        >
                            Skip for now
                        </button>
                    </div>
                )

            case 'text':
            default:
                return (
                    <form onSubmit={handleTextSubmit} className="text-input-form" aria-label="Text response">
                        <input
                            type="text"
                            value={currentMessage}
                            onChange={(e) => setCurrentMessage(e.target.value)}
                            placeholder="Type your response..."
                            disabled={isLoading}
                            autoFocus
                            className="text-input"
                            aria-label="Your response"
                        />
                        <button
                            type="submit"
                            disabled={!currentMessage.trim() || isLoading}
                            className="send-button"
                            aria-label={isLoading ? "Sending message" : "Send message"}
                        >
                            {isLoading ? (
                                <span className="loading-dots" aria-hidden="true">...</span>
                            ) : (
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                                    <line x1="22" y1="2" x2="11" y2="13" />
                                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                                </svg>
                            )}
                        </button>
                    </form>
                )
        }
    }

    return (
        <div className="fnol-input-container" role="form" aria-label="Claim form input">
            {validationErrors.length > 0 && (
                <div className="validation-errors" role="alert" aria-live="assertive">
                    {validationErrors.map((error, index) => (
                        <div key={index} className="error-message">
                            {error}
                        </div>
                    ))}
                </div>
            )}

            {renderInput()}

            <style>{`
                .fnol-input-container {
                    padding: 16px;
                    background: white;
                    border-top: 1px solid #e2e8f0;
                }

                .validation-errors {
                    margin-bottom: 12px;
                }

                .error-message {
                    padding: 8px 12px;
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    border-radius: 6px;
                    color: #dc2626;
                    font-size: 13px;
                    margin-bottom: 4px;
                }

                .option-buttons {
                    display: flex;
                    gap: 12px;
                    flex-wrap: wrap;
                }

                .select-options {
                    flex-direction: column;
                }

                .option-button {
                    flex: 1;
                    min-width: 120px;
                    padding: 12px 20px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.2s;
                    border: 2px solid #e2e8f0;
                    background: white;
                    color: #334155;
                }

                .option-button:hover:not(:disabled) {
                    border-color: #0066cc;
                    background: #f0f7ff;
                }

                .option-button.primary {
                    background: #0066cc;
                    color: white;
                    border-color: #0066cc;
                }

                .option-button.primary:hover:not(:disabled) {
                    background: #0052a3;
                }

                .option-button.secondary {
                    background: #f8fafc;
                }

                .option-button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .multiselect-container {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }

                .checkbox-group {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    border: none;
                    padding: 0;
                    margin: 0;
                }

                .checkbox-option {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 10px 12px;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.2s;
                }

                .checkbox-option:hover {
                    background: #f8fafc;
                }

                .checkbox-option input {
                    width: 18px;
                    height: 18px;
                }

                .text-input-form {
                    display: flex;
                    gap: 8px;
                }

                .text-input,
                .date-input,
                .time-input {
                    flex: 1;
                    padding: 12px 16px;
                    border: 2px solid #e2e8f0;
                    border-radius: 8px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.2s;
                }

                .text-input:focus,
                .date-input:focus,
                .time-input:focus {
                    border-color: #0066cc;
                }

                .send-button {
                    width: 44px;
                    height: 44px;
                    border-radius: 8px;
                    background: #0066cc;
                    color: white;
                    border: none;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: background 0.2s;
                }

                .send-button:hover:not(:disabled) {
                    background: #0052a3;
                }

                .send-button:disabled {
                    background: #94a3b8;
                    cursor: not-allowed;
                }

                .send-button svg {
                    width: 20px;
                    height: 20px;
                }

                .submit-button {
                    padding: 12px 24px;
                    background: #0066cc;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.2s;
                }

                .submit-button:hover:not(:disabled) {
                    background: #0052a3;
                }

                .submit-button:disabled {
                    background: #94a3b8;
                    cursor: not-allowed;
                }

                .photo-input {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }

                .hidden {
                    display: none;
                }

                .photo-button {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    padding: 16px 24px;
                    background: #0066cc;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.2s;
                }

                .photo-button svg {
                    width: 20px;
                    height: 20px;
                }

                .photo-button:hover:not(:disabled) {
                    background: #0052a3;
                }

                .skip-button {
                    padding: 10px;
                    background: transparent;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    color: #64748b;
                    font-size: 13px;
                    cursor: pointer;
                }

                .skip-button:hover {
                    background: #f8fafc;
                }

                .loading-dots {
                    display: inline-block;
                    animation: pulse 1s infinite;
                }

                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `}</style>
        </div>
    )
}

export default FNOLDynamicInput
