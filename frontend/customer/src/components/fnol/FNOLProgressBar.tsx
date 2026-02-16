import React from 'react'
import { useFNOLStore, STATE_LABELS, FNOLStateName } from '../../stores/fnolStore'

// States to show in progress bar (excluding terminal states)
const VISIBLE_STATES: FNOLStateName[] = [
    'SAFETY_CHECK',
    'IDENTITY_MATCH',
    'INCIDENT_CORE',
    'VEHICLE_DRIVER',
    'THIRD_PARTIES',
    'INJURIES',
    'DAMAGE_EVIDENCE',
    'CLAIM_CREATE',
    'NEXT_STEPS',
]

interface ProgressStepProps {
    state: FNOLStateName
    isCompleted: boolean
    isCurrent: boolean
    isLast: boolean
}

const ProgressStep: React.FC<ProgressStepProps> = ({
    state,
    isCompleted,
    isCurrent,
    isLast,
}) => {
    const label = STATE_LABELS[state]

    return (
        <div className="fnol-progress-step">
            <div className={`step-indicator ${isCompleted ? 'completed' : ''} ${isCurrent ? 'current' : ''}`}>
                {isCompleted ? (
                    <svg className="check-icon" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                ) : (
                    <span className="step-number">{VISIBLE_STATES.indexOf(state) + 1}</span>
                )}
            </div>
            <span className={`step-label ${isCurrent ? 'current' : ''}`}>{label}</span>
            {!isLast && <div className={`step-connector ${isCompleted ? 'completed' : ''}`} />}
        </div>
    )
}

export const FNOLProgressBar: React.FC = () => {
    const { currentState, completedStates, progressPercent } = useFNOLStore()

    return (
        <div className="fnol-progress-bar">
            <div className="progress-header">
                <span className="progress-title">Claim Progress</span>
                <span className="progress-percent">{progressPercent}%</span>
            </div>

            <div className="progress-track">
                <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
            </div>

            <div className="progress-steps">
                {VISIBLE_STATES.map((state, index) => (
                    <ProgressStep
                        key={state}
                        state={state}
                        isCompleted={completedStates.includes(state)}
                        isCurrent={state === currentState}
                        isLast={index === VISIBLE_STATES.length - 1}
                    />
                ))}
            </div>

            <style>{`
                .fnol-progress-bar {
                    padding: 16px 20px;
                    background: #ffffff;
                    border-bottom: 1px solid #e5e7eb;
                }

                .progress-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }

                .progress-title {
                    font-size: 15px;
                    font-weight: 600;
                    color: #1f2937;
                }

                .progress-percent {
                    font-size: 16px;
                    font-weight: 600;
                    color: #0066cc;
                    background: #eff6ff;
                    padding: 4px 10px;
                    border-radius: 12px;
                }

                .progress-track {
                    height: 8px;
                    background: #e5e7eb;
                    border-radius: 4px;
                    overflow: hidden;
                    margin-bottom: 16px;
                }

                .progress-fill {
                    height: 100%;
                    background: #0066cc;
                    border-radius: 4px;
                    transition: width 0.3s ease;
                }

                .progress-steps {
                    display: flex;
                    gap: 4px;
                    overflow-x: auto;
                    padding-bottom: 4px;
                    background: transparent;
                }

                .progress-steps::-webkit-scrollbar {
                    height: 4px;
                }

                .progress-steps::-webkit-scrollbar-track {
                    background: #f3f4f6;
                }

                .progress-steps::-webkit-scrollbar-thumb {
                    background: #d1d5db;
                    border-radius: 2px;
                }

                .fnol-progress-step {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    flex-shrink: 0;
                    min-width: 70px;
                    padding: 0;
                    margin: 0;
                    background: transparent !important;
                    border: none !important;
                    outline: none !important;
                    box-shadow: none !important;
                }

                .fnol-progress-step::before,
                .fnol-progress-step::after {
                    display: none !important;
                }

                .step-indicator {
                    width: 32px;
                    height: 32px;
                    min-width: 32px;
                    min-height: 32px;
                    max-width: 32px;
                    max-height: 32px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: #e5e7eb !important;
                    color: #6b7280;
                    font-size: 13px;
                    font-weight: 600;
                    flex-shrink: 0;
                    transition: all 0.2s ease;
                    margin: 0 0 6px 0;
                    padding: 0;
                    border: none !important;
                    outline: none !important;
                    box-shadow: none !important;
                    box-sizing: border-box;
                }

                .step-indicator::before,
                .step-indicator::after {
                    display: none !important;
                }

                .step-indicator.completed {
                    background: #22c55e !important;
                    color: white;
                }

                .step-indicator.current {
                    background: #0066cc !important;
                    color: white;
                }

                .check-icon {
                    width: 16px;
                    height: 16px;
                }

                .step-label {
                    font-size: 11px;
                    font-weight: 500;
                    color: #6b7280;
                    text-align: center;
                    line-height: 1.2;
                    max-width: 70px;
                }

                .step-label.current {
                    color: #0066cc;
                    font-weight: 600;
                }

                .step-connector {
                    display: none;
                }

                @media (max-width: 768px) {
                    .fnol-progress-bar {
                        padding: 12px 16px;
                    }

                    .progress-title {
                        font-size: 14px;
                    }

                    .progress-percent {
                        font-size: 14px;
                        padding: 3px 8px;
                    }

                    .progress-track {
                        height: 6px;
                    }

                    .fnol-progress-step {
                        min-width: 60px;
                        padding: 3px;
                        background: none;
                        border: none;
                    }

                    .step-indicator {
                        width: 28px;
                        height: 28px;
                        font-size: 12px;
                        margin-bottom: 5px;
                    }

                    .step-label {
                        font-size: 10px;
                        max-width: 60px;
                    }
                }
            `}</style>
        </div>
    )
}

export default FNOLProgressBar
