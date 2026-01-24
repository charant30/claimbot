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

const DOC_TYPES = [
    { value: 'police_report', label: 'Police report' },
    { value: 'photo', label: 'Incident photos' },
    { value: 'estimate', label: 'Repair estimate' },
    { value: 'invoice', label: 'Invoice' },
    { value: 'other', label: 'Other' },
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

    return (
        <div className="document-panel">
            <h4>Upload supporting documents</h4>
            <p className="document-panel-subtitle">
                Claim <strong>{claimId}</strong> needs documents like a police report or photos.
            </p>

            <div className="document-actions">
                {DOC_TYPES.map((type) => (
                    <label key={type.value} className="document-upload">
                        <span>{type.label}</span>
                        <input
                            type="file"
                            data-doc-type={type.value}
                            onChange={handleFileChange}
                            disabled={isLoading}
                            accept="image/*,.pdf"
                        />
                    </label>
                ))}
            </div>

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
