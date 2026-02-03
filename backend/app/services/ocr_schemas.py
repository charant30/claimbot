"""
OCR Extraction Schemas - Document-specific Pydantic models for structured extraction.
"""
from typing import List, Optional, Any
from decimal import Decimal
from pydantic import BaseModel, Field


class PoliceReportExtraction(BaseModel):
    """Extracted data from a police report document."""
    police_report_number: Optional[str] = Field(
        None, description="The official police report number/ID"
    )
    incident_date: Optional[str] = Field(
        None, description="Date of the incident (YYYY-MM-DD format preferred)"
    )
    incident_time: Optional[str] = Field(
        None, description="Time of the incident"
    )
    incident_location: Optional[str] = Field(
        None, description="Location/address where the incident occurred"
    )
    incident_description: Optional[str] = Field(
        None, description="Brief description of what happened"
    )
    parties_involved: List[str] = Field(
        default_factory=list, description="Names of parties involved"
    )
    officer_name: Optional[str] = Field(
        None, description="Name of the reporting officer"
    )
    officer_badge: Optional[str] = Field(
        None, description="Badge number of the reporting officer"
    )
    citation_issued: Optional[bool] = Field(
        None, description="Whether a citation was issued"
    )
    fault_determination: Optional[str] = Field(
        None, description="Who was determined to be at fault, if stated"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score for extraction quality"
    )


class RepairEstimateExtraction(BaseModel):
    """Extracted data from a repair estimate document."""
    estimate_number: Optional[str] = Field(
        None, description="The estimate reference number"
    )
    estimate_date: Optional[str] = Field(
        None, description="Date the estimate was created"
    )
    shop_name: Optional[str] = Field(
        None, description="Name of the repair shop"
    )
    shop_address: Optional[str] = Field(
        None, description="Address of the repair shop"
    )
    shop_phone: Optional[str] = Field(
        None, description="Phone number of the repair shop"
    )
    vehicle_info: Optional[str] = Field(
        None, description="Vehicle make/model/year if visible"
    )
    repair_items: List[dict] = Field(
        default_factory=list,
        description="List of repair items with description and cost"
    )
    parts_total: Optional[str] = Field(
        None, description="Total cost of parts"
    )
    labor_total: Optional[str] = Field(
        None, description="Total cost of labor"
    )
    total_amount: Optional[str] = Field(
        None, description="Total estimate amount"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score for extraction quality"
    )


class InvoiceExtraction(BaseModel):
    """Extracted data from an invoice document."""
    invoice_number: Optional[str] = Field(
        None, description="Invoice number/ID"
    )
    invoice_date: Optional[str] = Field(
        None, description="Date of the invoice"
    )
    vendor_name: Optional[str] = Field(
        None, description="Name of the vendor/business"
    )
    vendor_address: Optional[str] = Field(
        None, description="Address of the vendor"
    )
    line_items: List[dict] = Field(
        default_factory=list,
        description="List of line items with description and amount"
    )
    subtotal: Optional[str] = Field(
        None, description="Subtotal before tax"
    )
    tax_amount: Optional[str] = Field(
        None, description="Tax amount"
    )
    total_amount: Optional[str] = Field(
        None, description="Total invoice amount"
    )
    payment_status: Optional[str] = Field(
        None, description="Payment status (paid, pending, etc.)"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score for extraction quality"
    )


class IncidentPhotoExtraction(BaseModel):
    """Extracted data from incident photos."""
    photo_date: Optional[str] = Field(
        None, description="Date photo was taken (from EXIF or visible)"
    )
    location_visible: Optional[str] = Field(
        None, description="Any visible location information"
    )
    damage_description: Optional[str] = Field(
        None, description="Description of visible damage"
    )
    damage_severity: Optional[str] = Field(
        None, description="Estimated severity (minor, moderate, severe, total loss)"
    )
    vehicle_visible: Optional[bool] = Field(
        None, description="Whether a vehicle is visible in the photo"
    )
    vehicle_info: Optional[str] = Field(
        None, description="Vehicle make/model if identifiable"
    )
    license_plate: Optional[str] = Field(
        None, description="License plate if visible"
    )
    summary: Optional[str] = Field(
        None, description="Overall summary of what the photo shows"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score for extraction quality"
    )


class MedicalEOBExtraction(BaseModel):
    """Extracted data from Explanation of Benefits (EOB) document."""
    eob_number: Optional[str] = Field(
        None, description="EOB reference number"
    )
    service_date: Optional[str] = Field(
        None, description="Date of medical service"
    )
    patient_name: Optional[str] = Field(
        None, description="Patient name"
    )
    provider_name: Optional[str] = Field(
        None, description="Healthcare provider name"
    )
    provider_npi: Optional[str] = Field(
        None, description="Provider NPI number"
    )
    diagnosis_codes: List[str] = Field(
        default_factory=list, description="ICD diagnosis codes"
    )
    procedure_codes: List[str] = Field(
        default_factory=list, description="CPT procedure codes"
    )
    billed_amount: Optional[str] = Field(
        None, description="Amount billed by provider"
    )
    allowed_amount: Optional[str] = Field(
        None, description="Insurance allowed amount"
    )
    patient_responsibility: Optional[str] = Field(
        None, description="Amount patient owes"
    )
    plan_paid: Optional[str] = Field(
        None, description="Amount insurance paid"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score for extraction quality"
    )


class MedicalRecordExtraction(BaseModel):
    """Extracted data from medical records."""
    record_date: Optional[str] = Field(
        None, description="Date of the medical record"
    )
    patient_name: Optional[str] = Field(
        None, description="Patient name"
    )
    provider_name: Optional[str] = Field(
        None, description="Healthcare provider name"
    )
    facility_name: Optional[str] = Field(
        None, description="Medical facility name"
    )
    visit_type: Optional[str] = Field(
        None, description="Type of visit (emergency, routine, etc.)"
    )
    diagnosis: Optional[str] = Field(
        None, description="Diagnosis or condition"
    )
    treatment: Optional[str] = Field(
        None, description="Treatment provided"
    )
    medications: List[str] = Field(
        default_factory=list, description="Medications prescribed"
    )
    follow_up: Optional[str] = Field(
        None, description="Follow-up instructions"
    )
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score for extraction quality"
    )


# Mapping of document types to their extraction schemas
DOC_TYPE_SCHEMA_MAP = {
    "police_report": PoliceReportExtraction,
    "repair_estimate": RepairEstimateExtraction,
    "invoice": InvoiceExtraction,
    "incident_photos": IncidentPhotoExtraction,
    "photo": IncidentPhotoExtraction,
    "eob": MedicalEOBExtraction,
    "medical_record": MedicalRecordExtraction,
    "medical_records": MedicalRecordExtraction,
}


def get_extraction_prompt_for_doc_type(doc_type: str) -> str:
    """
    Get a document-specific extraction prompt.

    Args:
        doc_type: The type of document being processed

    Returns:
        A detailed prompt for the LLM to extract structured data
    """
    base_prompt = "You are an OCR extraction assistant. Extract structured details from the uploaded document image. "

    if doc_type == "police_report":
        return base_prompt + """
This is a POLICE REPORT. Extract the following if visible:
- police_report_number: The official report number/case number
- incident_date: Date of the incident (use YYYY-MM-DD format)
- incident_time: Time of incident
- incident_location: Full address or location description
- incident_description: Brief summary of what happened
- parties_involved: List of names of all parties
- officer_name: Reporting officer's name
- officer_badge: Badge number
- citation_issued: true/false if mentioned
- fault_determination: Who was at fault if stated
- confidence: Your confidence in the extraction (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot find."""

    elif doc_type == "repair_estimate":
        return base_prompt + """
This is a REPAIR ESTIMATE. Extract the following if visible:
- estimate_number: Reference number
- estimate_date: Date of estimate (YYYY-MM-DD)
- shop_name: Repair shop name
- shop_address: Shop address
- shop_phone: Shop phone number
- vehicle_info: Vehicle year/make/model
- repair_items: List of items as [{"description": "...", "cost": "..."}]
- parts_total: Total parts cost
- labor_total: Total labor cost
- total_amount: Grand total
- confidence: Your confidence (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot find."""

    elif doc_type == "invoice":
        return base_prompt + """
This is an INVOICE. Extract the following if visible:
- invoice_number: Invoice number/ID
- invoice_date: Date (YYYY-MM-DD)
- vendor_name: Business/vendor name
- vendor_address: Vendor address
- line_items: List as [{"description": "...", "amount": "..."}]
- subtotal: Subtotal amount
- tax_amount: Tax amount
- total_amount: Total amount due
- payment_status: Paid/pending if shown
- confidence: Your confidence (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot find."""

    elif doc_type in ["incident_photos", "photo"]:
        return base_prompt + """
This is an INCIDENT PHOTO. Analyze and extract:
- photo_date: Date if visible in image or EXIF
- location_visible: Any visible location markers/signs
- damage_description: Detailed description of visible damage
- damage_severity: minor/moderate/severe/total_loss
- vehicle_visible: true/false
- vehicle_info: Make/model if identifiable
- license_plate: If visible
- summary: Overall description of what the photo shows
- confidence: Your confidence (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot determine."""

    elif doc_type == "eob":
        return base_prompt + """
This is an EXPLANATION OF BENEFITS (EOB). Extract:
- eob_number: EOB reference number
- service_date: Date of service (YYYY-MM-DD)
- patient_name: Patient's name
- provider_name: Healthcare provider name
- provider_npi: NPI number if shown
- diagnosis_codes: List of ICD codes
- procedure_codes: List of CPT codes
- billed_amount: Amount billed
- allowed_amount: Allowed amount
- patient_responsibility: Patient owes
- plan_paid: Insurance paid
- confidence: Your confidence (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot find."""

    elif doc_type in ["medical_record", "medical_records"]:
        return base_prompt + """
This is a MEDICAL RECORD. Extract:
- record_date: Date of record (YYYY-MM-DD)
- patient_name: Patient name
- provider_name: Provider name
- facility_name: Medical facility
- visit_type: Type of visit
- diagnosis: Primary diagnosis
- treatment: Treatment provided
- medications: List of medications
- follow_up: Follow-up instructions
- confidence: Your confidence (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot find."""

    else:
        # Generic extraction for unknown document types
        return base_prompt + """
Extract any relevant information from this document:
- summary: Brief summary of the document
- dates: List of any dates found
- parties: List of any names/parties mentioned
- amounts: List of any monetary amounts
- document_ids: Any reference numbers or IDs
- incident_location: Location if mentioned
- confidence: Your confidence (0.0 to 1.0)

Return ONLY valid JSON. Use null for fields you cannot find."""


def validate_extraction(doc_type: str, extracted: dict) -> dict:
    """
    Validate and normalize extracted data using the appropriate schema.

    Args:
        doc_type: The document type
        extracted: Raw extracted dictionary

    Returns:
        Validated and normalized dictionary
    """
    schema_class = DOC_TYPE_SCHEMA_MAP.get(doc_type)

    if schema_class:
        try:
            # Validate through Pydantic model
            validated = schema_class(**extracted)
            return validated.model_dump()
        except Exception:
            # If validation fails, return original with status
            return {**extracted, "validation_status": "partial"}

    # For unknown types, return as-is
    return extracted
