"""
ClaimDraft and related models for FNOL (First Notice of Loss) system.

These models implement the canonical claim schema from the FNOL specification,
supporting incremental data collection during the conversation flow.
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Column, String, Date, DateTime, Time, Enum, ForeignKey,
    Numeric, Boolean, Text, Integer
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.models.fnol_enums import (
    ClaimDraftStatus, TriageRoute, LossType, VehicleRole, PartyRole,
    InjurySeverity, TreatmentLevel, EvidenceType, DamageArea, DamageType,
    ImpactType, PoliceContactStatus, DrivableStatus, PolicyMatchStatus,
    FNOLState as FNOLStateEnum
)


class ClaimDraft(Base):
    """
    Main claim draft model for FNOL intake.

    This is a versioned, validated payload that supports incremental updates
    during the conversation flow. It can be converted to a full Claim record
    upon successful submission.
    """
    __tablename__ = "claim_drafts"

    # Primary key
    claim_draft_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Session tracking
    thread_id = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)

    # Status and state machine position
    status = Column(Enum(ClaimDraftStatus), default=ClaimDraftStatus.IN_PROGRESS, nullable=False)
    current_state = Column(Enum(FNOLStateEnum), default=FNOLStateEnum.SAFETY_CHECK, nullable=False)
    state_data = Column(JSON, default=dict)  # Temporary data for current state

    # Policy matching
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.policy_id"), nullable=True)
    policy_match_status = Column(Enum(PolicyMatchStatus), default=PolicyMatchStatus.PENDING)
    policy_match_method = Column(String(50))  # policy_number, phone_lookup, name_dob, guest
    policy_match_confidence = Column(Numeric(3, 2), default=0)

    # Core incident information
    loss_type = Column(Enum(LossType), nullable=True)
    loss_subtype = Column(String(50))  # Specific scenario: two_vehicle, hail, etc.
    incident_date = Column(Date, nullable=True)
    incident_time = Column(Time, nullable=True)
    incident_time_approximate = Column(Boolean, default=False)  # User said "around 6pm"
    incident_location_raw = Column(String(500))  # User-provided text
    incident_location_normalized = Column(String(500))  # Geocoded address
    incident_lat = Column(Numeric(10, 7))
    incident_lng = Column(Numeric(10, 7))
    incident_description = Column(Text)  # Narrative from user

    # Scenario classification
    primary_scenario = Column(String(50))  # e.g., "collision_two_vehicle"
    secondary_scenarios = Column(JSON, default=list)  # Additional applicable playbooks
    scenario_flags = Column(JSON, default=list)  # Detected flags for routing

    # Police information
    police_contacted = Column(Enum(PoliceContactStatus))
    police_report_number = Column(String(100))
    police_agency = Column(String(200))
    police_officer_name = Column(String(200))
    police_officer_badge = Column(String(50))
    citation_issued = Column(Boolean)
    dui_suspected = Column(Boolean)

    # Triage result
    triage_route = Column(Enum(TriageRoute))
    triage_score = Column(Integer)
    triage_reasons = Column(JSON, default=list)
    triage_rule_version = Column(String(20), default="v1")

    # Converted claim reference
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.claim_id"), nullable=True)
    claim_number = Column(String(50))  # Assigned after conversion

    # Resume/continuation support
    resume_token = Column(String(100), unique=True, nullable=True)
    resume_expires_at = Column(DateTime, nullable=True)

    # Consents collected
    consents = Column(JSON, default=list)  # List of {type, timestamp, text}
    fraud_acknowledgment = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    policy = relationship("Policy", foreign_keys=[policy_id])
    claim = relationship("Claim", foreign_keys=[claim_id])
    vehicles = relationship("ClaimDraftVehicle", back_populates="claim_draft", cascade="all, delete-orphan")
    parties = relationship("ClaimDraftParty", back_populates="claim_draft", cascade="all, delete-orphan")
    impacts = relationship("ClaimDraftImpact", back_populates="claim_draft", cascade="all, delete-orphan")
    injuries = relationship("ClaimDraftInjury", back_populates="claim_draft", cascade="all, delete-orphan")
    damages = relationship("ClaimDraftDamage", back_populates="claim_draft", cascade="all, delete-orphan")
    evidence = relationship("ClaimDraftEvidence", back_populates="claim_draft", cascade="all, delete-orphan")
    audit_log = relationship("ClaimDraftAudit", back_populates="claim_draft", cascade="all, delete-orphan", order_by="ClaimDraftAudit.timestamp")

    def __repr__(self) -> str:
        return f"<ClaimDraft {self.claim_draft_id} ({self.status.value})>"

    def to_canonical_dict(self) -> dict:
        """Convert to canonical schema format for API responses."""
        return {
            "claimDraftId": str(self.claim_draft_id),
            "status": self.status.value,
            "policyMatch": {
                "status": self.policy_match_status.value if self.policy_match_status else None,
                "policyId": str(self.policy_id) if self.policy_id else None,
                "method": self.policy_match_method,
            },
            "incident": {
                "lossType": self.loss_type.value if self.loss_type else None,
                "occurredAt": self.incident_date.isoformat() if self.incident_date else None,
                "location": {
                    "raw": self.incident_location_raw,
                    "normalized": self.incident_location_normalized,
                    "lat": float(self.incident_lat) if self.incident_lat else None,
                    "lng": float(self.incident_lng) if self.incident_lng else None,
                },
                "description": self.incident_description,
            },
            "vehicles": [v.to_dict() for v in self.vehicles],
            "parties": [p.to_dict() for p in self.parties],
            "impacts": [i.to_dict() for i in self.impacts],
            "injuries": [i.to_dict() for i in self.injuries],
            "damages": [d.to_dict() for d in self.damages],
            "evidence": [e.to_dict() for e in self.evidence],
            "police": {
                "contacted": self.police_contacted.value if self.police_contacted else None,
                "reportNumber": self.police_report_number,
                "agency": self.police_agency,
            },
            "triage": {
                "route": self.triage_route.value if self.triage_route else None,
                "score": self.triage_score,
                "reasons": self.triage_reasons,
                "ruleVersion": self.triage_rule_version,
            },
            "audit": {
                "consents": self.consents,
                "fraudAcknowledged": self.fraud_acknowledgment,
            },
        }


class ClaimDraftVehicle(Base):
    """Vehicle information for a claim draft."""
    __tablename__ = "claim_draft_vehicles"

    vehicle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)

    # Vehicle role in incident
    vehicle_role = Column(Enum(VehicleRole), nullable=False)

    # Vehicle identification
    vin = Column(String(17))
    year = Column(Integer)
    make = Column(String(100))
    model = Column(String(100))
    trim = Column(String(100))
    color = Column(String(50))
    license_plate = Column(String(20))
    license_state = Column(String(10))

    # Source of vehicle info
    from_policy = Column(Boolean, default=False)  # Selected from policy vehicles
    policy_vehicle_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to PolicyVehicle

    # Vehicle status
    drivable = Column(Enum(DrivableStatus))
    current_location = Column(String(500))  # Where vehicle is now
    tow_needed = Column(Boolean, default=False)
    tow_destination = Column(String(500))

    # For rental vehicles
    is_rental = Column(Boolean, default=False)
    rental_company = Column(String(200))
    rental_agreement_number = Column(String(100))

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="vehicles")
    parties = relationship("ClaimDraftParty", back_populates="vehicle")
    damages = relationship("ClaimDraftDamage", back_populates="vehicle")

    def __repr__(self) -> str:
        return f"<ClaimDraftVehicle {self.year} {self.make} {self.model} ({self.vehicle_role.value})>"

    def to_dict(self) -> dict:
        return {
            "vehicleId": str(self.vehicle_id),
            "role": self.vehicle_role.value,
            "vin": self.vin,
            "year": self.year,
            "make": self.make,
            "model": self.model,
            "color": self.color,
            "plate": self.license_plate,
            "plateState": self.license_state,
            "drivable": self.drivable.value if self.drivable else None,
            "currentLocation": self.current_location,
            "towNeeded": self.tow_needed,
            "isRental": self.is_rental,
            "rentalCompany": self.rental_company,
        }


class ClaimDraftParty(Base):
    """Party (person) information for a claim draft."""
    __tablename__ = "claim_draft_parties"

    party_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("claim_draft_vehicles.vehicle_id"), nullable=True)

    # Party role
    party_role = Column(Enum(PartyRole), nullable=False)

    # Personal information
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    email = Column(String(255))
    date_of_birth = Column(Date)

    # Driver information
    drivers_license = Column(String(50))
    drivers_license_state = Column(String(10))
    relationship_to_insured = Column(String(100))  # self, spouse, child, friend, etc.
    has_permission = Column(Boolean)  # Permission to drive insured vehicle

    # Third-party insurance info
    insurance_carrier = Column(String(200))
    insurance_policy_number = Column(String(100))
    insurance_claim_number = Column(String(100))

    # Unknown party marker (for hit-and-run)
    is_unknown = Column(Boolean, default=False)
    unknown_description = Column(Text)  # Partial plate, vehicle description, etc.

    # Contact preferences
    preferred_contact_method = Column(String(20))  # phone, email, text
    best_callback_time = Column(String(100))

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="parties")
    vehicle = relationship("ClaimDraftVehicle", back_populates="parties")
    injuries = relationship("ClaimDraftInjury", back_populates="party")

    def __repr__(self) -> str:
        if self.is_unknown:
            return f"<ClaimDraftParty Unknown ({self.party_role.value})>"
        return f"<ClaimDraftParty {self.first_name} {self.last_name} ({self.party_role.value})>"

    def to_dict(self) -> dict:
        return {
            "partyId": str(self.party_id),
            "role": self.party_role.value,
            "name": f"{self.first_name or ''} {self.last_name or ''}".strip() or None,
            "phone": self.phone,
            "email": self.email,
            "vehicleId": str(self.vehicle_id) if self.vehicle_id else None,
            "isUnknown": self.is_unknown,
            "insuranceCarrier": self.insurance_carrier,
            "insurancePolicyNumber": self.insurance_policy_number,
        }


class ClaimDraftImpact(Base):
    """Impact relationship between vehicles."""
    __tablename__ = "claim_draft_impacts"

    impact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)

    # Impact participants (nullable for unknown in hit-and-run)
    from_vehicle_id = Column(UUID(as_uuid=True), ForeignKey("claim_draft_vehicles.vehicle_id"), nullable=True)
    to_vehicle_id = Column(UUID(as_uuid=True), ForeignKey("claim_draft_vehicles.vehicle_id"), nullable=True)

    # Impact details
    impact_type = Column(Enum(ImpactType))
    from_vehicle_unknown = Column(Boolean, default=False)
    to_vehicle_unknown = Column(Boolean, default=False)
    description = Column(Text)

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="impacts")
    from_vehicle = relationship("ClaimDraftVehicle", foreign_keys=[from_vehicle_id])
    to_vehicle = relationship("ClaimDraftVehicle", foreign_keys=[to_vehicle_id])

    def to_dict(self) -> dict:
        return {
            "impactId": str(self.impact_id),
            "fromVehicleId": str(self.from_vehicle_id) if self.from_vehicle_id else "unknown",
            "toVehicleId": str(self.to_vehicle_id) if self.to_vehicle_id else "unknown",
            "type": self.impact_type.value if self.impact_type else None,
            "description": self.description,
        }


class ClaimDraftInjury(Base):
    """Injury information for a party in the claim."""
    __tablename__ = "claim_draft_injuries"

    injury_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)
    party_id = Column(UUID(as_uuid=True), ForeignKey("claim_draft_parties.party_id"), nullable=False)

    # Injury details
    severity = Column(Enum(InjurySeverity), default=InjurySeverity.UNKNOWN)
    treatment_level = Column(Enum(TreatmentLevel), default=TreatmentLevel.NONE)
    description = Column(Text)  # Brief description, not detailed medical
    body_part = Column(String(100))  # General area: head, neck, back, etc.

    # Emergency response
    ambulance_called = Column(Boolean, default=False)
    hospitalized = Column(Boolean, default=False)
    hospital_name = Column(String(200))

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="injuries")
    party = relationship("ClaimDraftParty", back_populates="injuries")

    def to_dict(self) -> dict:
        return {
            "injuryId": str(self.injury_id),
            "partyId": str(self.party_id),
            "severity": self.severity.value if self.severity else None,
            "treatment": self.treatment_level.value if self.treatment_level else None,
            "ambulanceCalled": self.ambulance_called,
            "hospitalized": self.hospitalized,
            "hospitalName": self.hospital_name,
        }


class ClaimDraftDamage(Base):
    """Damage information for vehicles or property."""
    __tablename__ = "claim_draft_damages"

    damage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("claim_draft_vehicles.vehicle_id"), nullable=True)

    # Damage classification
    damage_type = Column(Enum(DamageType), nullable=False)
    damage_area = Column(Enum(DamageArea))  # For vehicle damage

    # Damage details
    description = Column(Text)
    estimated_amount = Column(Numeric(12, 2))
    pre_existing = Column(Boolean, default=False)
    pre_existing_description = Column(Text)

    # For property damage (non-vehicle)
    property_type = Column(String(100))  # fence, mailbox, building, etc.
    property_owner_name = Column(String(200))
    property_owner_contact = Column(String(200))
    property_address = Column(String(500))

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="damages")
    vehicle = relationship("ClaimDraftVehicle", back_populates="damages")

    def to_dict(self) -> dict:
        return {
            "damageId": str(self.damage_id),
            "vehicleId": str(self.vehicle_id) if self.vehicle_id else None,
            "type": self.damage_type.value if self.damage_type else None,
            "area": self.damage_area.value if self.damage_area else None,
            "description": self.description,
            "estimatedAmount": float(self.estimated_amount) if self.estimated_amount else None,
            "preExisting": self.pre_existing,
            "propertyType": self.property_type,
        }


class ClaimDraftEvidence(Base):
    """Evidence/document reference for a claim draft."""
    __tablename__ = "claim_draft_evidence"

    evidence_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)

    # Reference to uploaded document
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id"), nullable=True)

    # Evidence classification
    evidence_type = Column(Enum(EvidenceType), nullable=False)
    subtype = Column(String(50))  # More specific categorization

    # Evidence metadata
    description = Column(Text)
    captured_at = Column(DateTime)  # When the evidence was captured/created

    # AI extraction results
    extracted_entities = Column(JSON, default=dict)
    extraction_confidence = Column(Numeric(3, 2))

    # Upload status
    upload_status = Column(String(20), default="pending")  # pending, uploaded, verified, failed
    upload_url = Column(String(500))  # Pre-signed upload URL
    storage_url = Column(String(500))  # Final storage location

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    uploaded_at = Column(DateTime)

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="evidence")
    document = relationship("Document")

    def to_dict(self) -> dict:
        return {
            "evidenceId": str(self.evidence_id),
            "type": self.evidence_type.value if self.evidence_type else None,
            "subtype": self.subtype,
            "description": self.description,
            "status": self.upload_status,
            "documentId": str(self.document_id) if self.document_id else None,
        }


class ClaimDraftAudit(Base):
    """Audit trail for claim draft changes."""
    __tablename__ = "claim_draft_audit"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_draft_id = Column(UUID(as_uuid=True), ForeignKey("claim_drafts.claim_draft_id"), nullable=False)

    # Event details
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    state = Column(String(50))  # State machine state when event occurred
    action = Column(String(100), nullable=False)  # What happened
    actor = Column(String(100), nullable=False)  # Who/what triggered: user, system, llm:intent, etc.

    # Change tracking
    field_changed = Column(String(100))  # Which field was changed
    data_before = Column(JSON)  # Previous value
    data_after = Column(JSON)  # New value

    # AI confidence (if action involved AI)
    confidence = Column(Numeric(3, 2))

    # User input that triggered this
    user_input = Column(Text)

    # Relationships
    claim_draft = relationship("ClaimDraft", back_populates="audit_log")

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "state": self.state,
            "action": self.action,
            "actor": self.actor,
            "field": self.field_changed,
            "confidence": float(self.confidence) if self.confidence else None,
        }
