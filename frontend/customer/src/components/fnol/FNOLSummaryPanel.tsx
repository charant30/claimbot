import React from 'react'
import { FNOLSummaryResponse } from '../../services/api'

interface FNOLSummaryPanelProps {
    summary: FNOLSummaryResponse
    onConfirm: () => void
    onEdit: () => void
    isLoading?: boolean
}

export const FNOLSummaryPanel: React.FC<FNOLSummaryPanelProps> = ({
    summary,
    onConfirm,
    onEdit,
    isLoading = false,
}) => {
    const { summary: data, can_submit, validation_errors } = summary

    const formatDate = (dateStr: string | undefined) => {
        if (!dateStr) return 'Not provided'
        try {
            return new Date(dateStr).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
            })
        } catch {
            return dateStr
        }
    }

    const formatTime = (timeStr: string | undefined) => {
        if (!timeStr) return ''
        return timeStr
    }

    return (
        <div className="fnol-summary-panel" role="region" aria-label="Claim summary">
            <div className="summary-header">
                <div className="summary-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path fillRule="evenodd" d="M7.502 6h7.128A3.375 3.375 0 0118 9.375v9.375a3 3 0 003-3V6.108c0-1.505-1.125-2.811-2.664-2.94a48.972 48.972 0 00-.673-.05A3 3 0 0015 1.5h-1.5a3 3 0 00-2.663 1.618c-.225.015-.45.032-.673.05C8.662 3.295 7.554 4.542 7.502 6zM13.5 3A1.5 1.5 0 0012 4.5h4.5A1.5 1.5 0 0015 3h-1.5z" clipRule="evenodd" />
                        <path fillRule="evenodd" d="M3 9.375C3 8.339 3.84 7.5 4.875 7.5h9.75c1.036 0 1.875.84 1.875 1.875v11.25c0 1.035-.84 1.875-1.875 1.875h-9.75A1.875 1.875 0 013 20.625V9.375zM6 12a.75.75 0 01.75-.75h.008a.75.75 0 01.75.75v.008a.75.75 0 01-.75.75H6.75a.75.75 0 01-.75-.75V12zm2.25 0a.75.75 0 01.75-.75h3.75a.75.75 0 010 1.5H9a.75.75 0 01-.75-.75zM6 15a.75.75 0 01.75-.75h.008a.75.75 0 01.75.75v.008a.75.75 0 01-.75.75H6.75a.75.75 0 01-.75-.75V15zm2.25 0a.75.75 0 01.75-.75h3.75a.75.75 0 010 1.5H9a.75.75 0 01-.75-.75zM6 18a.75.75 0 01.75-.75h.008a.75.75 0 01.75.75v.008a.75.75 0 01-.75.75H6.75a.75.75 0 01-.75-.75V18zm2.25 0a.75.75 0 01.75-.75h3.75a.75.75 0 010 1.5H9a.75.75 0 01-.75-.75z" clipRule="evenodd" />
                    </svg>
                </div>
                <h2>Review Your Claim</h2>
                <p>Please verify the information below before submitting.</p>
            </div>

            {/* Validation Errors */}
            {validation_errors && validation_errors.length > 0 && (
                <div className="validation-errors" role="alert">
                    <h3>Missing Information</h3>
                    <ul>
                        {validation_errors.map((error, index) => (
                            <li key={index}>{error}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Incident Details */}
            <div className="summary-section">
                <h3>Incident Details</h3>
                <div className="summary-grid">
                    <div className="summary-item">
                        <span className="label">Date</span>
                        <span className="value">{formatDate(data?.incident?.date)}</span>
                    </div>
                    <div className="summary-item">
                        <span className="label">Time</span>
                        <span className="value">{formatTime(data?.incident?.time) || 'Not provided'}</span>
                    </div>
                    <div className="summary-item full-width">
                        <span className="label">Location</span>
                        <span className="value">{data?.incident?.location || 'Not provided'}</span>
                    </div>
                    <div className="summary-item full-width">
                        <span className="label">Description</span>
                        <span className="value">{data?.incident?.description || 'Not provided'}</span>
                    </div>
                </div>
            </div>

            {/* Vehicle Information */}
            {data?.vehicles && data.vehicles.length > 0 && (
                <div className="summary-section">
                    <h3>Vehicle Information</h3>
                    {data.vehicles.map((vehicle: any, index: number) => (
                        <div key={index} className="summary-card">
                            <div className="card-header">
                                <span className="card-badge">{vehicle.role || 'Insured'}</span>
                            </div>
                            <div className="summary-grid">
                                <div className="summary-item">
                                    <span className="label">Vehicle</span>
                                    <span className="value">
                                        {[vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(' ') || 'Not provided'}
                                    </span>
                                </div>
                                <div className="summary-item">
                                    <span className="label">Color</span>
                                    <span className="value">{vehicle.color || 'Not provided'}</span>
                                </div>
                                <div className="summary-item">
                                    <span className="label">License Plate</span>
                                    <span className="value">{vehicle.license_plate || 'Not provided'}</span>
                                </div>
                                <div className="summary-item">
                                    <span className="label">Drivable</span>
                                    <span className="value">{vehicle.is_drivable ? 'Yes' : 'No'}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Parties Involved */}
            {data?.parties && data.parties.length > 0 && (
                <div className="summary-section">
                    <h3>Parties Involved</h3>
                    {data.parties.map((party: any, index: number) => (
                        <div key={index} className="summary-card">
                            <div className="card-header">
                                <span className="card-badge">{party.role || 'Party'}</span>
                            </div>
                            <div className="summary-grid">
                                <div className="summary-item">
                                    <span className="label">Name</span>
                                    <span className="value">
                                        {[party.first_name, party.last_name].filter(Boolean).join(' ') || 'Not provided'}
                                    </span>
                                </div>
                                <div className="summary-item">
                                    <span className="label">Phone</span>
                                    <span className="value">{party.phone || 'Not provided'}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Injuries */}
            {data?.injuries && (
                <div className="summary-section">
                    <h3>Injuries</h3>
                    <div className="summary-grid">
                        <div className="summary-item">
                            <span className="label">Anyone Injured</span>
                            <span className="value">{data.injuries.any_injured ? 'Yes' : 'No'}</span>
                        </div>
                        {data.injuries.any_injured && (
                            <div className="summary-item">
                                <span className="label">Severity</span>
                                <span className="value">{data.injuries.severity || 'Not specified'}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Damage Information */}
            {data?.damage && (
                <div className="summary-section">
                    <h3>Damage Information</h3>
                    <div className="summary-grid">
                        {data.damage.areas && data.damage.areas.length > 0 && (
                            <div className="summary-item full-width">
                                <span className="label">Damaged Areas</span>
                                <span className="value">{data.damage.areas.join(', ')}</span>
                            </div>
                        )}
                        {data.damage.description && (
                            <div className="summary-item full-width">
                                <span className="label">Description</span>
                                <span className="value">{data.damage.description}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Evidence */}
            {data?.evidence && data.evidence.length > 0 && (
                <div className="summary-section">
                    <h3>Uploaded Evidence</h3>
                    <div className="evidence-list">
                        {data.evidence.map((item: any, index: number) => (
                            <div key={index} className="evidence-item">
                                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                    <path fillRule="evenodd" d="M1.5 6a2.25 2.25 0 012.25-2.25h16.5A2.25 2.25 0 0122.5 6v12a2.25 2.25 0 01-2.25 2.25H3.75A2.25 2.25 0 011.5 18V6zM3 16.06V18c0 .414.336.75.75.75h16.5A.75.75 0 0021 18v-1.94l-2.69-2.689a1.5 1.5 0 00-2.12 0l-.88.879.97.97a.75.75 0 11-1.06 1.06l-5.16-5.159a1.5 1.5 0 00-2.12 0L3 16.061zm10.125-7.81a1.125 1.125 0 112.25 0 1.125 1.125 0 01-2.25 0z" clipRule="evenodd" />
                                </svg>
                                <span>{item.type || 'Photo'}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Action Buttons */}
            <div className="summary-actions">
                <button
                    className="btn-secondary"
                    onClick={onEdit}
                    disabled={isLoading}
                >
                    Edit Information
                </button>
                <button
                    className="btn-primary"
                    onClick={onConfirm}
                    disabled={!can_submit || isLoading}
                >
                    {isLoading ? 'Submitting...' : 'Confirm & Submit'}
                </button>
            </div>

            {!can_submit && (
                <p className="submit-note">Please provide all required information before submitting.</p>
            )}

            <style>{`
                .fnol-summary-panel {
                    padding: 20px;
                    background: #f8fafc;
                    border-radius: 12px;
                    max-height: 70vh;
                    overflow-y: auto;
                }

                .summary-header {
                    text-align: center;
                    margin-bottom: 24px;
                }

                .summary-icon {
                    width: 48px;
                    height: 48px;
                    background: #e0f2fe;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 12px;
                }

                .summary-icon svg {
                    width: 24px;
                    height: 24px;
                    color: #0284c7;
                }

                .summary-header h2 {
                    margin: 0 0 4px;
                    font-size: 20px;
                    color: #1e293b;
                }

                .summary-header p {
                    margin: 0;
                    color: #64748b;
                    font-size: 14px;
                }

                .validation-errors {
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    border-radius: 8px;
                    padding: 12px 16px;
                    margin-bottom: 20px;
                }

                .validation-errors h3 {
                    margin: 0 0 8px;
                    font-size: 14px;
                    color: #dc2626;
                }

                .validation-errors ul {
                    margin: 0;
                    padding-left: 20px;
                }

                .validation-errors li {
                    color: #b91c1c;
                    font-size: 13px;
                    margin-bottom: 4px;
                }

                .summary-section {
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 16px;
                    margin-bottom: 16px;
                }

                .summary-section h3 {
                    margin: 0 0 12px;
                    font-size: 15px;
                    color: #1e293b;
                    font-weight: 600;
                }

                .summary-grid {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 12px;
                }

                .summary-item {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }

                .summary-item.full-width {
                    grid-column: 1 / -1;
                }

                .summary-item .label {
                    font-size: 12px;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }

                .summary-item .value {
                    font-size: 14px;
                    color: #1e293b;
                }

                .summary-card {
                    background: #f8fafc;
                    border-radius: 6px;
                    padding: 12px;
                    margin-bottom: 8px;
                }

                .summary-card:last-child {
                    margin-bottom: 0;
                }

                .card-header {
                    margin-bottom: 8px;
                }

                .card-badge {
                    display: inline-block;
                    padding: 2px 8px;
                    background: #e0f2fe;
                    color: #0284c7;
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 4px;
                    text-transform: uppercase;
                }

                .evidence-list {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                }

                .evidence-item {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 8px 12px;
                    background: #f1f5f9;
                    border-radius: 6px;
                    font-size: 13px;
                    color: #475569;
                }

                .evidence-item svg {
                    width: 16px;
                    height: 16px;
                    color: #64748b;
                }

                .summary-actions {
                    display: flex;
                    gap: 12px;
                    margin-top: 24px;
                }

                .btn-primary,
                .btn-secondary {
                    flex: 1;
                    padding: 12px 20px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                    border: none;
                }

                .btn-primary {
                    background: #0066cc;
                    color: white;
                }

                .btn-primary:hover:not(:disabled) {
                    background: #0052a3;
                }

                .btn-primary:disabled {
                    background: #94a3b8;
                    cursor: not-allowed;
                }

                .btn-secondary {
                    background: white;
                    color: #475569;
                    border: 1px solid #e2e8f0;
                }

                .btn-secondary:hover:not(:disabled) {
                    background: #f8fafc;
                    border-color: #cbd5e1;
                }

                .submit-note {
                    text-align: center;
                    margin-top: 12px;
                    font-size: 13px;
                    color: #94a3b8;
                }

                @media (max-width: 480px) {
                    .summary-grid {
                        grid-template-columns: 1fr;
                    }

                    .summary-actions {
                        flex-direction: column;
                    }
                }
            `}</style>
        </div>
    )
}

export default FNOLSummaryPanel
