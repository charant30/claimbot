"""
Documents API routes
"""
import os
import uuid
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Document, DocumentType, Claim, Policy
from app.core import get_current_user_id, settings, logger
from app.services.ocr import extract_document_entities

router = APIRouter()


# Response schemas
class DocumentResponse(BaseModel):
    doc_id: str
    claim_id: str
    doc_type: str
    filename: str
    storage_url: str
    extracted_entities: dict
    uploaded_at: str


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    claim_id: str = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Upload a document for a claim."""
    # Validate claim ownership
    claim = (
        db.query(Claim)
        .join(Policy)
        .filter(Claim.claim_id == claim_id, Policy.user_id == user_id)
        .first()
    )
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )
    
    # Validate file size
    file_content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )
    
    # Save file
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(claim.claim_id))
    os.makedirs(upload_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    stored_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_dir, stored_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    extracted_entities = await extract_document_entities(
        file_path=file_path,
        doc_type=doc_type,
        content_type=file.content_type,
        db=db,
    )

    # Create document record
    document = Document(
        claim_id=claim.claim_id,
        doc_type=DocumentType(doc_type),
        filename=file.filename or stored_filename,
        storage_url=file_path,
        content_type=file.content_type,
        file_size=f"{len(file_content) / 1024:.1f}KB",
        extracted_entities=extracted_entities,
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document uploaded: {document.filename} for claim {claim_id}")
    
    return DocumentResponse(
        doc_id=str(document.doc_id),
        claim_id=str(document.claim_id),
        doc_type=document.doc_type.value,
        filename=document.filename,
        storage_url=document.storage_url,
        extracted_entities=document.extracted_entities,
        uploaded_at=document.uploaded_at.isoformat(),
    )


@router.get("/claim/{claim_id}", response_model=List[DocumentResponse])
async def get_claim_documents(
    claim_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get all documents for a claim."""
    # Validate claim ownership
    claim = (
        db.query(Claim)
        .join(Policy)
        .filter(Claim.claim_id == claim_id, Policy.user_id == user_id)
        .first()
    )
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )
    
    return [
        DocumentResponse(
            doc_id=str(doc.doc_id),
            claim_id=str(doc.claim_id),
            doc_type=doc.doc_type.value,
            filename=doc.filename,
            storage_url=doc.storage_url,
            extracted_entities=doc.extracted_entities or {},
            uploaded_at=doc.uploaded_at.isoformat(),
        )
        for doc in claim.documents
    ]


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Delete a document."""
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Validate ownership through claim->policy->user
    claim = (
        db.query(Claim)
        .join(Policy)
        .filter(Claim.claim_id == document.claim_id, Policy.user_id == user_id)
        .first()
    )
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document",
        )
    
    # Delete file
    if os.path.exists(document.storage_url):
        os.remove(document.storage_url)
    
    # Delete record
    db.delete(document)
    db.commit()
    
    logger.info(f"Document deleted: {document.filename}")
    
    return {"message": "Document deleted"}
