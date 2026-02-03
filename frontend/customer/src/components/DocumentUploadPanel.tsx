interface DocumentItem {
    doc_id: string
    doc_type: string
    filename: string
    extracted_entities?: Record<string, any>
}

interface DocumentUploadPanelProps {
    claimId: string
    documents: DocumentItem[]
    isLoading: boolean
    onUpload: (docType: string, file: File) => void
}

// Document types matching backend - incident_photos is REQUIRED, police_report is OPTIONAL
const DOC_TYPES = [
    { value: 'incident_photos', label: 'Incident photos', required: true, description: 'Required - photos of damage' },
    { value: 'police_report', label: 'Police report', required: false, description: 'Optional - if available' },
    { value: 'repair_estimate', label: 'Repair estimate', required: false, description: 'Optional - for repair claims' },
    { value: 'invoice', label: 'Invoice', required: false, description: 'Optional - if repairs complete' },
]

function DocumentUploadPanel({ claimId, documents, isLoading, onUpload }: DocumentUploadPanelProps) {
    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        const docType = event.target.dataset.docType
        if (file && docType) {
            onUpload(docType, file)
            event.target.value = ''
        }
    }

    // Check if a document type has been uploaded
    const isDocTypeUploaded = (docType: string) => {
        return documents.some(doc => doc.doc_type === docType)
    }

    // Check if all required documents are uploaded
    const hasRequiredDocs = DOC_TYPES.filter(t => t.required).every(t => isDocTypeUploaded(t.value))

    return (
        <div className="document-panel">
            <h4>Upload supporting documents</h4>
            <p className="document-panel-subtitle">
                Claim <strong>{claimId.slice(0, 8)}...</strong> - Photos are required to verify the incident.
            </p>

            <div className="document-actions">
                {DOC_TYPES.map((type) => {
                    const uploaded = isDocTypeUploaded(type.value)
                    return (
                        <label
                            key={type.value}
                            className={`document-upload ${uploaded ? 'uploaded' : ''} ${type.required ? 'required' : ''}`}
                        >
                            <span className="doc-label">
                                {type.label}
                                {type.required && !uploaded && <span className="required-badge">*Required</span>}
                                {uploaded && <span className="uploaded-badge">Uploaded</span>}
                            </span>
                            <span className="doc-description">{type.description}</span>
                            <input
                                type="file"
                                data-doc-type={type.value}
                                onChange={handleFileChange}
                                disabled={isLoading || uploaded}
                                accept="image/*,.pdf"
                            />
                        </label>
                    )
                })}
            </div>

            {hasRequiredDocs && (
                <p className="document-panel-success">
                    Required documents uploaded. You can continue chatting or upload more documents.
                </p>
            )}

            {documents.length > 0 && (
                <div className="document-list">
                    <h5>Uploaded</h5>
                    <ul>
                        {documents.map((doc) => (
                            <li key={doc.doc_id}>
                                <span className="doc-name">{doc.filename}</span>
                                <span className="doc-type">{doc.doc_type.replace('_', ' ')}</span>
                                <span className="doc-status">
                                    {doc.extracted_entities?.status === 'processed'
                                        ? 'OCR processed'
                                        : doc.extracted_entities?.status || 'Uploaded'}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    )
}

export type { DocumentItem }
export default DocumentUploadPanel
