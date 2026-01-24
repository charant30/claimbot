import { useState } from 'react'

type ClaimFormData = {
    policyNumber: string
    incidentDate: string
    incidentType: string
    location: string
    description: string
    estimatedLoss: string
}

interface ClaimIntakeFormProps {
    onSubmit: (data: ClaimFormData) => void
    isLoading: boolean
}

const INCIDENT_TYPES = [
    { value: 'collision', label: 'Collision' },
    { value: 'theft', label: 'Theft' },
    { value: 'fire', label: 'Fire' },
    { value: 'weather', label: 'Weather' },
    { value: 'other', label: 'Other' },
]

function ClaimIntakeForm({ onSubmit, isLoading }: ClaimIntakeFormProps) {
    const [formData, setFormData] = useState<ClaimFormData>({
        policyNumber: '',
        incidentDate: '',
        incidentType: '',
        location: '',
        description: '',
        estimatedLoss: '',
    })

    const handleChange = (field: keyof ClaimFormData, value: string) => {
        setFormData((prev) => ({ ...prev, [field]: value }))
    }

    const handleSubmit = (event: React.FormEvent) => {
        event.preventDefault()
        onSubmit(formData)
    }

    return (
        <form className="claim-form" onSubmit={handleSubmit}>
            <h4>Claim details</h4>
            <p className="claim-form-subtitle">
                Provide the basics so we can verify your policy and start the claim.
            </p>

            <label>
                Policy number
                <input
                    type="text"
                    value={formData.policyNumber}
                    onChange={(event) => handleChange('policyNumber', event.target.value)}
                    placeholder="POL-123456"
                    required
                />
            </label>

            <label>
                Incident date
                <input
                    type="date"
                    value={formData.incidentDate}
                    onChange={(event) => handleChange('incidentDate', event.target.value)}
                    required
                />
            </label>

            <label>
                Incident type
                <select
                    value={formData.incidentType}
                    onChange={(event) => handleChange('incidentType', event.target.value)}
                    required
                >
                    <option value="">Select a type</option>
                    {INCIDENT_TYPES.map((type) => (
                        <option key={type.value} value={type.value}>
                            {type.label}
                        </option>
                    ))}
                </select>
            </label>

            <label>
                Location
                <input
                    type="text"
                    value={formData.location}
                    onChange={(event) => handleChange('location', event.target.value)}
                    placeholder="City, State"
                    required
                />
            </label>

            <label>
                Estimated loss amount
                <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={formData.estimatedLoss}
                    onChange={(event) => handleChange('estimatedLoss', event.target.value)}
                    placeholder="2500"
                    required
                />
            </label>

            <label>
                Description
                <textarea
                    value={formData.description}
                    onChange={(event) => handleChange('description', event.target.value)}
                    placeholder="Share a quick summary of what happened."
                    rows={3}
                    required
                />
            </label>

            <button type="submit" disabled={isLoading}>
                {isLoading ? 'Submitting...' : 'Submit claim details'}
            </button>
        </form>
    )
}

export type { ClaimFormData }
export default ClaimIntakeForm
