"""
Document Verification Service - Cross-document verification and consistency checks.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import re

from app.core.logging import logger


class DiscrepancySeverity(str, Enum):
    """Severity level of a discrepancy."""
    INFO = "info"           # Minor inconsistency, proceed
    WARNING = "warning"     # Notable inconsistency, flag for review
    ERROR = "error"         # Major inconsistency, requires human review


@dataclass
class Discrepancy:
    """A discrepancy found during cross-document verification."""
    type: str
    severity: DiscrepancySeverity
    field: str
    documents_involved: List[str]
    details: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity.value,
            "field": self.field,
            "documents_involved": self.documents_involved,
            "details": self.details,
            "recommendation": self.recommendation,
        }


@dataclass
class VerificationResult:
    """Result of cross-document verification."""
    is_valid: bool
    discrepancies: List[Discrepancy]
    verified_fields: Dict[str, Any]
    confidence_score: float

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "verified_fields": self.verified_fields,
            "confidence_score": self.confidence_score,
        }


def verify_cross_document_consistency(
    documents: List[Dict[str, Any]],
    collected_fields: Optional[Dict[str, Any]] = None,
    tolerance_days: int = 7,
) -> VerificationResult:
    """
    Verify consistency across multiple documents.

    Checks:
    - Date consistency (incident dates should match within tolerance)
    - Location consistency
    - Amount consistency (estimates vs invoices)
    - Party information consistency

    Args:
        documents: List of document dicts with extracted_entities
        collected_fields: Optional user-provided claim fields
        tolerance_days: Days of tolerance for date matching

    Returns:
        VerificationResult with discrepancies and verified fields
    """
    discrepancies = []
    verified_fields = {}
    confidence_scores = []

    # Extract entities from all documents
    doc_entities = {}
    for doc in documents:
        doc_type = doc.get("doc_type", "unknown")
        entities = doc.get("extracted_entities", {})
        if entities.get("status") not in ["error", "skipped"]:
            doc_entities[doc_type] = entities
            if "confidence" in entities:
                confidence_scores.append(float(entities.get("confidence", 0.5)))

    # Check date consistency
    date_discrepancies = _verify_date_consistency(doc_entities, collected_fields, tolerance_days)
    discrepancies.extend(date_discrepancies)

    # Check location consistency
    location_discrepancies = _verify_location_consistency(doc_entities, collected_fields)
    discrepancies.extend(location_discrepancies)

    # Check amount consistency
    amount_discrepancies = _verify_amount_consistency(doc_entities)
    discrepancies.extend(amount_discrepancies)

    # Check party information
    party_discrepancies = _verify_party_consistency(doc_entities, collected_fields)
    discrepancies.extend(party_discrepancies)

    # Build verified fields from consistent data
    verified_fields = _build_verified_fields(doc_entities, collected_fields)

    # Calculate overall confidence
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5

    # Adjust confidence based on discrepancies
    error_count = sum(1 for d in discrepancies if d.severity == DiscrepancySeverity.ERROR)
    warning_count = sum(1 for d in discrepancies if d.severity == DiscrepancySeverity.WARNING)
    adjusted_confidence = avg_confidence * (1 - error_count * 0.2 - warning_count * 0.1)
    adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

    # Determine overall validity
    is_valid = error_count == 0

    return VerificationResult(
        is_valid=is_valid,
        discrepancies=discrepancies,
        verified_fields=verified_fields,
        confidence_score=adjusted_confidence,
    )


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string into a datetime object."""
    if not date_str:
        return None

    # Common date formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return None


def _extract_dates_from_entities(entities: dict) -> List[str]:
    """Extract all date values from entity dictionary."""
    dates = []

    # Check common date field names
    date_fields = [
        "incident_date", "service_date", "estimate_date", "invoice_date",
        "photo_date", "record_date", "dates"
    ]

    for field in date_fields:
        value = entities.get(field)
        if value:
            if isinstance(value, list):
                dates.extend(value)
            else:
                dates.append(value)

    return dates


def _verify_date_consistency(
    doc_entities: Dict[str, dict],
    collected_fields: Optional[Dict[str, Any]],
    tolerance_days: int,
) -> List[Discrepancy]:
    """Verify that dates are consistent across documents."""
    discrepancies = []
    all_dates = {}

    # Collect dates from all documents
    for doc_type, entities in doc_entities.items():
        dates = _extract_dates_from_entities(entities)
        for date_str in dates:
            parsed = _parse_date(date_str)
            if parsed:
                all_dates.setdefault(doc_type, []).append(parsed)

    # Also check user-provided incident date
    if collected_fields and collected_fields.get("incident_date"):
        parsed = _parse_date(collected_fields["incident_date"])
        if parsed:
            all_dates.setdefault("user_provided", []).append(parsed)

    # Compare dates across sources
    if len(all_dates) > 1:
        all_parsed_dates = [d for dates in all_dates.values() for d in dates]
        if all_parsed_dates:
            min_date = min(all_parsed_dates)
            max_date = max(all_parsed_dates)
            date_diff = (max_date - min_date).days

            if date_diff > tolerance_days:
                discrepancies.append(Discrepancy(
                    type="date_mismatch",
                    severity=DiscrepancySeverity.WARNING if date_diff <= tolerance_days * 2 else DiscrepancySeverity.ERROR,
                    field="incident_date",
                    documents_involved=list(all_dates.keys()),
                    details=f"Dates vary by {date_diff} days (tolerance: {tolerance_days} days)",
                    recommendation="Verify the correct incident date with the customer",
                ))

    return discrepancies


def _verify_location_consistency(
    doc_entities: Dict[str, dict],
    collected_fields: Optional[Dict[str, Any]],
) -> List[Discrepancy]:
    """Verify that locations are consistent across documents."""
    discrepancies = []
    locations = {}

    # Collect locations from documents
    location_fields = ["incident_location", "location", "location_visible"]
    for doc_type, entities in doc_entities.items():
        for field in location_fields:
            value = entities.get(field)
            if value and isinstance(value, str) and len(value) > 5:
                locations[doc_type] = value.lower().strip()
                break

    # Add user-provided location
    if collected_fields:
        loc = collected_fields.get("incident_location") or collected_fields.get("location")
        if loc:
            locations["user_provided"] = loc.lower().strip()

    # Simple comparison - check if locations are significantly different
    if len(locations) > 1:
        unique_locations = list(set(locations.values()))
        if len(unique_locations) > 1:
            # Check for overlap in location strings
            common_words = _find_common_words(unique_locations)
            if not common_words:
                discrepancies.append(Discrepancy(
                    type="location_mismatch",
                    severity=DiscrepancySeverity.WARNING,
                    field="incident_location",
                    documents_involved=list(locations.keys()),
                    details=f"Locations appear different across documents",
                    recommendation="Verify the incident location with the customer",
                ))

    return discrepancies


def _find_common_words(strings: List[str]) -> set:
    """Find common significant words across strings."""
    if not strings:
        return set()

    # Split into words and filter short/common words
    stop_words = {"the", "a", "an", "at", "on", "in", "of", "to", "and", "or"}
    word_sets = []

    for s in strings:
        words = set(w for w in re.findall(r'\w+', s.lower()) if len(w) > 2 and w not in stop_words)
        word_sets.append(words)

    # Find intersection
    if word_sets:
        common = word_sets[0]
        for ws in word_sets[1:]:
            common = common.intersection(ws)
        return common

    return set()


def _verify_amount_consistency(doc_entities: Dict[str, dict]) -> List[Discrepancy]:
    """Verify that amounts are consistent between estimates and invoices."""
    discrepancies = []

    # Extract amounts
    amounts = {}
    amount_fields = ["total_amount", "estimated_damage", "billed_amount"]

    for doc_type, entities in doc_entities.items():
        for field in amount_fields:
            value = entities.get(field)
            if value:
                parsed = _parse_amount(value)
                if parsed:
                    amounts[doc_type] = parsed
                    break

    # Compare estimate to invoice
    estimate_amount = amounts.get("repair_estimate")
    invoice_amount = amounts.get("invoice")

    if estimate_amount and invoice_amount:
        diff_pct = abs(estimate_amount - invoice_amount) / estimate_amount * 100
        if diff_pct > 20:  # More than 20% difference
            discrepancies.append(Discrepancy(
                type="amount_mismatch",
                severity=DiscrepancySeverity.WARNING if diff_pct <= 30 else DiscrepancySeverity.ERROR,
                field="total_amount",
                documents_involved=["repair_estimate", "invoice"],
                details=f"Estimate (${estimate_amount:,.2f}) differs from invoice (${invoice_amount:,.2f}) by {diff_pct:.1f}%",
                recommendation="Verify the reason for the difference in amounts",
            ))

    return discrepancies


def _parse_amount(value: Any) -> Optional[float]:
    """Parse an amount value to float."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Remove currency symbols and commas
        cleaned = re.sub(r'[^\d.]', '', value)
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _verify_party_consistency(
    doc_entities: Dict[str, dict],
    collected_fields: Optional[Dict[str, Any]],
) -> List[Discrepancy]:
    """Verify party information consistency."""
    discrepancies = []

    # This is a placeholder for more sophisticated party matching
    # In production, you would compare names, addresses, etc.

    parties = {}
    for doc_type, entities in doc_entities.items():
        party_value = entities.get("parties_involved") or entities.get("parties")
        if party_value:
            if isinstance(party_value, list):
                parties[doc_type] = party_value
            else:
                parties[doc_type] = [party_value]

    # Add user-provided info
    if collected_fields and collected_fields.get("other_party_info"):
        parties["user_provided"] = [collected_fields["other_party_info"]]

    # For now, just flag if we have party info from multiple sources
    # More sophisticated matching would go here
    if len(parties) > 1:
        logger.info(f"Party information found in multiple documents: {list(parties.keys())}")

    return discrepancies


def _build_verified_fields(
    doc_entities: Dict[str, dict],
    collected_fields: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a dictionary of verified fields from all sources."""
    verified = {}

    # Priority order for field sources (highest priority first)
    source_priority = ["police_report", "repair_estimate", "invoice", "incident_photos", "eob"]

    # Field mapping
    field_sources = {
        "incident_date": ["incident_date", "service_date", "estimate_date"],
        "incident_location": ["incident_location", "location", "location_visible"],
        "police_report_number": ["police_report_number"],
        "estimated_damage": ["total_amount", "estimated_damage", "billed_amount"],
    }

    for target_field, source_fields in field_sources.items():
        for doc_type in source_priority:
            if doc_type in doc_entities:
                entities = doc_entities[doc_type]
                for source_field in source_fields:
                    value = entities.get(source_field)
                    if value:
                        verified[target_field] = value
                        verified[f"{target_field}_source"] = doc_type
                        break
                if target_field in verified:
                    break

    return verified


def generate_verification_summary(result: VerificationResult) -> str:
    """
    Generate a human-readable verification summary.

    Args:
        result: The verification result

    Returns:
        A summary string for display to agents or users
    """
    lines = []

    if result.is_valid:
        lines.append("Document verification completed successfully.")
    else:
        lines.append("Document verification found issues requiring attention.")

    lines.append(f"\nConfidence Score: {result.confidence_score:.0%}")

    if result.discrepancies:
        lines.append("\nDiscrepancies Found:")
        for d in result.discrepancies:
            severity_icon = {"error": "!!!", "warning": "!!", "info": "i"}.get(d.severity.value, "?")
            lines.append(f"  [{severity_icon}] {d.details}")
            lines.append(f"      Recommendation: {d.recommendation}")

    if result.verified_fields:
        lines.append("\nVerified Fields:")
        for field, value in result.verified_fields.items():
            if not field.endswith("_source"):
                source = result.verified_fields.get(f"{field}_source", "unknown")
                lines.append(f"  - {field}: {value} (from {source})")

    return "\n".join(lines)
