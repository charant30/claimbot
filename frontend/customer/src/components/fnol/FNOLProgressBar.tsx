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
                    padding: 16px;
                    background: #f8fafc;
                    border-bottom: 1px solid #e2e8f0;
                }

                .progress-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }

                .progress-title {
                    font-size: 14px;
                    font-weight: 600;
                    color: #334155;
                }

                .progress-percent {
                    font-size: 14px;
                    font-weight: 500;
                    color: #0066cc;
                }

                .progress-track {
                    height: 6px;
                    background: #e2e8f0;
                    border-radius: 3px;
                    overflow: hidden;
                    margin-bottom: 16px;
                }

                .progress-fill {
                    height: 100%;
                    background: linear-gradient(90deg, #0066cc, #0099ff);
                    border-radius: 3px;
                    transition: width 0.3s ease;
                }

                .progress-steps {
                    display: flex;
                    overflow-x: auto;
                    padding-bottom: 4px;
                }

                .fnol-progress-step {
                    display: flex;
                    align-items: center;
                    flex-shrink: 0;
                }

                .step-indicator {
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: #e2e8f0;
                    color: #64748b;
                    font-size: 12px;
                    font-weight: 600;
                    flex-shrink: 0;
                }

                .step-indicator.completed {
                    background: #22c55e;
                    color: white;
                }

                .step-indicator.current {
                    background: #0066cc;
                    color: white;
                    box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.2);
                }

                .check-icon {
                    width: 14px;
                    height: 14px;
                }

                .step-label {
                    margin-left: 6px;
                    font-size: 11px;
                    color: #64748b;
                    white-space: nowrap;
                }

                .step-label.current {
                    color: #0066cc;
                    font-weight: 600;
                }

                .step-connector {
                    width: 20px;
                    height: 2px;
                    background: #e2e8f0;
                    margin: 0 4px;
                    flex-shrink: 0;
                }

                .step-connector.completed {
                    background: #22c55e;
                }

                @media (max-width: 768px) {
                    .progress-steps {
                        display: none;
                    }
                }
            `}</style>
        </div>
    )
}

export default FNOLProgressBar
