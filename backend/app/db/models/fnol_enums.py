"""
FNOL (First Notice of Loss) Enumeration Types

These enums define the valid values for various fields in the FNOL claim draft system.
"""
from enum import Enum as PyEnum


class ClaimDraftStatus(str, PyEnum):
    """Status of a claim draft through the FNOL process."""
    IN_PROGRESS = "in_progress"      # User is actively filling out the claim
    PENDING_REVIEW = "pending_review"  # Awaiting user confirmation
    SUBMITTED = "submitted"           # User submitted, awaiting processing
    CONVERTED = "converted"           # Converted to actual Claim record
    ABANDONED = "abandoned"           # User abandoned the session


class TriageRoute(str, PyEnum):
    """Routing decision from triage engine."""
    STP = "stp"                # Straight-through processing (automated)
    ADJUSTER = "adjuster"      # Route to human adjuster
    SIU_REVIEW = "siu_review"  # Special Investigations Unit review
    EMERGENCY = "emergency"     # Emergency/priority handling


class LossType(str, PyEnum):
    """Primary type of loss/incident."""
    COLLISION = "collision"
    THEFT = "theft"
    WEATHER = "weather"
    GLASS = "glass"
    FIRE = "fire"
    VANDALISM = "vandalism"
    OTHER = "other"


class CollisionType(str, PyEnum):
    """Sub-type for collision incidents."""
    TWO_VEHICLE = "two_vehicle"
    SINGLE_VEHICLE = "single_vehicle"
    MULTI_VEHICLE = "multi_vehicle"
    HIT_AND_RUN = "hit_and_run"
    PARKING_LOT = "parking_lot"
    ANIMAL_STRIKE = "animal_strike"


class WeatherType(str, PyEnum):
    """Sub-type for weather-related incidents."""
    HAIL = "hail"
    FLOOD = "flood"
    WIND = "wind"
    TREE = "tree"


class TheftType(str, PyEnum):
    """Sub-type for theft incidents."""
    VEHICLE_STOLEN = "vehicle_stolen"
    ATTEMPTED_THEFT = "attempted_theft"
    ITEMS_STOLEN = "items_stolen"


class VehicleRole(str, PyEnum):
    """Role of a vehicle in the incident."""
    INSURED = "insured"          # The policyholder's vehicle
    THIRD_PARTY = "third_party"  # Other party's vehicle
    UNKNOWN = "unknown"          # Unknown vehicle (hit-and-run)


class PartyRole(str, PyEnum):
    """Role of a party (person) in the incident."""
    INSURED = "insured"                    # The policyholder
    INSURED_DRIVER = "insured_driver"      # Driver of insured vehicle
    INSURED_PASSENGER = "insured_passenger"  # Passenger in insured vehicle
    THIRD_PARTY_DRIVER = "third_party_driver"
    THIRD_PARTY_PASSENGER = "third_party_passenger"
    WITNESS = "witness"
    PEDESTRIAN = "pedestrian"
    PROPERTY_OWNER = "property_owner"      # Owner of damaged property
    REPORTER = "reporter"                   # Person reporting (if different from driver)


class InjurySeverity(str, PyEnum):
    """Severity level of reported injuries."""
    NONE = "none"
    UNKNOWN = "unknown"          # User unsure - treat as positive
    MINOR = "minor"              # No medical treatment needed
    MODERATE = "moderate"        # Outpatient treatment
    SEVERE = "severe"            # Hospitalization required
    FATAL = "fatal"


class TreatmentLevel(str, PyEnum):
    """Level of medical treatment received."""
    NONE = "none"
    ONSITE = "onsite"            # First aid at scene
    URGENT_CARE = "urgent_care"  # Walk-in clinic
    ER = "er"                    # Emergency room
    ADMITTED = "admitted"        # Hospital admission


class EvidenceType(str, PyEnum):
    """Type of evidence/document uploaded."""
    PHOTO = "photo"
    VIDEO = "video"
    POLICE_REPORT = "police_report"
    WITNESS_STATEMENT = "witness_statement"
    MEDICAL_RECORD = "medical_record"
    REPAIR_ESTIMATE = "repair_estimate"
    TOW_BILL = "tow_bill"
    RENTAL_RECEIPT = "rental_receipt"
    DASHCAM = "dashcam"
    OTHER = "other"


class EvidenceSubtype(str, PyEnum):
    """Subtype for evidence categorization."""
    # Photo subtypes
    SCENE = "scene"
    DAMAGE = "damage"
    VIN_STICKER = "vin_sticker"
    LICENSE_PLATE = "license_plate"
    PAINT_TRANSFER = "paint_transfer"
    DEBRIS = "debris"
    # Document subtypes
    EXCHANGE_SLIP = "exchange_slip"
    INSURANCE_CARD = "insurance_card"
    DRIVERS_LICENSE = "drivers_license"


class DamageArea(str, PyEnum):
    """Area of vehicle damage."""
    FRONT = "front"
    REAR = "rear"
    LEFT_SIDE = "left_side"
    RIGHT_SIDE = "right_side"
    ROOF = "roof"
    HOOD = "hood"
    TRUNK = "trunk"
    WINDSHIELD = "windshield"
    SIDE_WINDOW = "side_window"
    REAR_WINDOW = "rear_window"
    UNDERCARRIAGE = "undercarriage"
    INTERIOR = "interior"
    TOTAL = "total"  # Total loss
    OTHER = "other"


class DamageType(str, PyEnum):
    """Type of damage."""
    VEHICLE = "vehicle"
    PROPERTY = "property"         # Third-party property
    PERSONAL_PROPERTY = "personal_property"  # Items in vehicle


class ImpactType(str, PyEnum):
    """Type of vehicle impact."""
    REAR_END = "rear_end"
    FRONT_END = "front_end"
    SIDESWIPE = "sideswipe"
    T_BONE = "t_bone"
    HEAD_ON = "head_on"
    ROLLOVER = "rollover"
    UNKNOWN = "unknown"


class PoliceContactStatus(str, PyEnum):
    """Status of police involvement."""
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
    PENDING = "pending"  # User plans to file report


class DrivableStatus(str, PyEnum):
    """Whether the vehicle is drivable."""
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class PolicyMatchStatus(str, PyEnum):
    """Result of policy matching attempt."""
    MATCHED = "matched"
    GUEST = "guest"        # No match, proceeding as guest
    FAILED = "failed"      # Match attempted but failed verification
    PENDING = "pending"    # OTP or other verification pending


class FNOLState(str, PyEnum):
    """Top-level states in the FNOL state machine."""
    SAFETY_CHECK = "SAFETY_CHECK"
    IDENTITY_MATCH = "IDENTITY_MATCH"
    INCIDENT_CORE = "INCIDENT_CORE"
    LOSS_MODULE = "LOSS_MODULE"
    VEHICLE_DRIVER = "VEHICLE_DRIVER"
    THIRD_PARTIES = "THIRD_PARTIES"
    INJURIES = "INJURIES"
    DAMAGE_EVIDENCE = "DAMAGE_EVIDENCE"
    TRIAGE = "TRIAGE"
    CLAIM_CREATE = "CLAIM_CREATE"
    NEXT_STEPS = "NEXT_STEPS"
    HANDOFF_ESCALATION = "HANDOFF_ESCALATION"


class UseType(str, PyEnum):
    """Vehicle use type at time of incident."""
    PERSONAL = "personal"
    COMMERCIAL = "commercial"
    RIDESHARE = "rideshare"
    DELIVERY = "delivery"
    RENTAL = "rental"
