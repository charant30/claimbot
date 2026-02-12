"""
Entity Extraction Service

Extracts structured entities from user input for FNOL data collection.
This is a bounded AI task - output is schema-constrained.

Extractable entities:
- Dates and times
- Locations/addresses
- Vehicle information (make, model, year, color, VIN, plate)
- Person information (names, phone, email)
- Injury indicators
- Damage descriptions
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import date, time, datetime
import re
import os


@dataclass
class ExtractedValue:
    """A single extracted value with confidence."""
    value: Any
    confidence: float
    source_text: str = ""

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source_text": self.source_text,
        }


@dataclass
class ExtractedEntities:
    """Container for all extracted entities."""
    # Temporal
    date: Optional[ExtractedValue] = None
    time: Optional[ExtractedValue] = None

    # Location
    location: Optional[ExtractedValue] = None
    city: Optional[ExtractedValue] = None
    state: Optional[ExtractedValue] = None
    zip_code: Optional[ExtractedValue] = None

    # Vehicle
    vehicle_year: Optional[ExtractedValue] = None
    vehicle_make: Optional[ExtractedValue] = None
    vehicle_model: Optional[ExtractedValue] = None
    vehicle_color: Optional[ExtractedValue] = None
    vehicle_vin: Optional[ExtractedValue] = None
    license_plate: Optional[ExtractedValue] = None
    license_state: Optional[ExtractedValue] = None

    # Person
    first_name: Optional[ExtractedValue] = None
    last_name: Optional[ExtractedValue] = None
    full_name: Optional[ExtractedValue] = None
    phone: Optional[ExtractedValue] = None
    email: Optional[ExtractedValue] = None

    # Incident
    loss_type: Optional[ExtractedValue] = None
    injury_mentioned: Optional[ExtractedValue] = None
    damage_areas: List[ExtractedValue] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {}
        for key, value in self.__dict__.items():
            if value is None:
                continue
            if isinstance(value, list):
                if value:
                    result[key] = [v.to_dict() for v in value]
            elif isinstance(value, ExtractedValue):
                result[key] = value.to_dict()
        return result

    def has_any(self) -> bool:
        """Check if any entities were extracted."""
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, list) and value:
                    return True
                elif isinstance(value, ExtractedValue):
                    return True
        return False


class ExtractionService:
    """
    Service for extracting structured entities from text.

    Uses regex patterns for common formats and optionally
    LLM for complex extractions.
    """

    # US States abbreviations
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    }

    # Common vehicle makes
    VEHICLE_MAKES = {
        "toyota", "honda", "ford", "chevrolet", "chevy", "nissan", "hyundai",
        "kia", "subaru", "mazda", "volkswagen", "vw", "bmw", "mercedes",
        "audi", "lexus", "acura", "infiniti", "dodge", "jeep", "ram",
        "gmc", "buick", "cadillac", "chrysler", "tesla", "volvo", "porsche",
    }

    # Common vehicle colors
    VEHICLE_COLORS = {
        "black", "white", "silver", "gray", "grey", "red", "blue", "green",
        "brown", "tan", "beige", "gold", "yellow", "orange", "purple",
        "maroon", "burgundy", "navy", "charcoal",
    }

    # Loss type keywords
    LOSS_TYPE_KEYWORDS = {
        "collision": ["crash", "hit", "collision", "accident", "rear-end", "t-bone", "sideswipe"],
        "theft": ["stolen", "theft", "break-in", "broke into"],
        "weather": ["hail", "flood", "storm", "wind", "tree", "lightning"],
        "vandalism": ["vandal", "keyed", "graffiti", "smashed"],
        "glass": ["windshield", "window", "glass"],
        "fire": ["fire", "burned", "flames"],
    }

    # Damage area keywords
    DAMAGE_AREAS = {
        "front": ["front", "bumper", "hood", "headlight", "grille"],
        "rear": ["rear", "back", "trunk", "taillight", "bumper"],
        "left_side": ["left", "driver side", "driver's side"],
        "right_side": ["right", "passenger side", "passenger's side"],
        "roof": ["roof", "top"],
        "windshield": ["windshield", "front window"],
        "side_window": ["side window", "door window"],
    }

    def __init__(self, use_llm: bool = False):
        """Initialize extraction service."""
        self.use_llm = use_llm
        self._llm_client = None

    def extract(
        self,
        text: str,
        target_fields: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractedEntities:
        """
        Extract entities from text.

        Args:
            text: User's input text
            target_fields: Optional list of specific fields to extract
            context: Optional context (current state, pending question)

        Returns:
            ExtractedEntities with all found values
        """
        entities = ExtractedEntities()
        text_lower = text.lower()

        # Always extract these
        self._extract_date(text, entities)
        self._extract_time(text, entities)
        self._extract_phone(text, entities)
        self._extract_email(text, entities)
        self._extract_zip(text, entities)
        self._extract_state(text, entities)

        # Extract based on target fields or all
        if not target_fields or "vehicle" in target_fields:
            self._extract_vehicle_info(text, entities)

        if not target_fields or "location" in target_fields:
            self._extract_location(text, entities)

        if not target_fields or "name" in target_fields:
            self._extract_name(text, entities)

        if not target_fields or "loss_type" in target_fields:
            self._extract_loss_type(text_lower, entities)

        if not target_fields or "injury" in target_fields:
            self._extract_injury_mention(text_lower, entities)

        if not target_fields or "damage" in target_fields:
            self._extract_damage_areas(text_lower, entities)

        return entities

    def _extract_date(self, text: str, entities: ExtractedEntities):
        """Extract date from text."""
        # MM/DD/YYYY or MM-DD-YYYY
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text)
        if match:
            month, day, year = match.groups()
            year = int(year)
            if year < 100:
                year += 2000
            try:
                d = date(year, int(month), int(day))
                entities.date = ExtractedValue(
                    value=d.isoformat(),
                    confidence=0.95,
                    source_text=match.group(),
                )
                return
            except ValueError:
                pass

        # YYYY-MM-DD (ISO format)
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        if match:
            try:
                d = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                entities.date = ExtractedValue(
                    value=d.isoformat(),
                    confidence=0.95,
                    source_text=match.group(),
                )
                return
            except ValueError:
                pass

        # Natural language dates (yesterday, today, last week, etc.)
        text_lower = text.lower()
        today = date.today()

        if "yesterday" in text_lower:
            from datetime import timedelta
            d = today - timedelta(days=1)
            entities.date = ExtractedValue(
                value=d.isoformat(),
                confidence=0.9,
                source_text="yesterday",
            )
        elif "today" in text_lower:
            entities.date = ExtractedValue(
                value=today.isoformat(),
                confidence=0.9,
                source_text="today",
            )

    def _extract_time(self, text: str, entities: ExtractedEntities):
        """Extract time from text."""
        # HH:MM AM/PM
        match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', text, re.IGNORECASE)
        if match:
            hour, minute, period = match.groups()
            hour = int(hour)
            minute = int(minute)

            if period:
                period = period.lower()
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0

            try:
                t = time(hour, minute)
                entities.time = ExtractedValue(
                    value=t.strftime("%H:%M"),
                    confidence=0.9,
                    source_text=match.group(),
                )
            except ValueError:
                pass

        # Natural language times
        text_lower = text.lower()
        time_words = {
            "morning": "09:00",
            "noon": "12:00",
            "afternoon": "14:00",
            "evening": "18:00",
            "night": "21:00",
            "midnight": "00:00",
        }
        for word, time_val in time_words.items():
            if word in text_lower:
                entities.time = ExtractedValue(
                    value=time_val,
                    confidence=0.6,
                    source_text=word,
                )
                break

    def _extract_phone(self, text: str, entities: ExtractedEntities):
        """Extract phone number from text."""
        # Various phone formats
        patterns = [
            r'(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})',
            r'\((\d{3})\)\s*(\d{3})[-.\s]?(\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                digits = "".join(match.groups())
                entities.phone = ExtractedValue(
                    value=digits,
                    confidence=0.95,
                    source_text=match.group(),
                )
                return

    def _extract_email(self, text: str, entities: ExtractedEntities):
        """Extract email from text."""
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if match:
            entities.email = ExtractedValue(
                value=match.group().lower(),
                confidence=0.98,
                source_text=match.group(),
            )

    def _extract_zip(self, text: str, entities: ExtractedEntities):
        """Extract ZIP code from text."""
        match = re.search(r'\b(\d{5})(?:-\d{4})?\b', text)
        if match:
            entities.zip_code = ExtractedValue(
                value=match.group(1),
                confidence=0.9,
                source_text=match.group(),
            )

    def _extract_state(self, text: str, entities: ExtractedEntities):
        """Extract US state from text."""
        text_upper = text.upper()
        for state in self.US_STATES:
            if re.search(rf'\b{state}\b', text_upper):
                entities.state = ExtractedValue(
                    value=state,
                    confidence=0.85,
                    source_text=state,
                )
                return

    def _extract_vehicle_info(self, text: str, entities: ExtractedEntities):
        """Extract vehicle information from text."""
        text_lower = text.lower()

        # Year (4 digits between 1990-2030)
        match = re.search(r'\b(19[9]\d|20[0-3]\d)\b', text)
        if match:
            entities.vehicle_year = ExtractedValue(
                value=int(match.group()),
                confidence=0.85,
                source_text=match.group(),
            )

        # Make
        for make in self.VEHICLE_MAKES:
            if re.search(rf'\b{make}\b', text_lower):
                # Normalize
                normalized = make.title()
                if make == "chevy":
                    normalized = "Chevrolet"
                elif make == "vw":
                    normalized = "Volkswagen"
                entities.vehicle_make = ExtractedValue(
                    value=normalized,
                    confidence=0.9,
                    source_text=make,
                )
                break

        # Color
        for color in self.VEHICLE_COLORS:
            if re.search(rf'\b{color}\b', text_lower):
                entities.vehicle_color = ExtractedValue(
                    value=color.title(),
                    confidence=0.9,
                    source_text=color,
                )
                break

        # VIN (17 alphanumeric, excluding I, O, Q)
        match = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', text.upper())
        if match:
            entities.vehicle_vin = ExtractedValue(
                value=match.group(),
                confidence=0.95,
                source_text=match.group(),
            )

        # License plate (various formats)
        match = re.search(r'\b([A-Z]{1,3}[-\s]?\d{1,4}[-\s]?[A-Z]{0,3}|\d{1,3}[-\s]?[A-Z]{3})\b', text.upper())
        if match and len(match.group().replace("-", "").replace(" ", "")) >= 4:
            entities.license_plate = ExtractedValue(
                value=match.group().replace(" ", "").replace("-", ""),
                confidence=0.7,
                source_text=match.group(),
            )

    def _extract_location(self, text: str, entities: ExtractedEntities):
        """Extract location/address from text."""
        # Street address pattern
        match = re.search(
            r'(\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|way|circle|cir|court|ct))',
            text,
            re.IGNORECASE,
        )
        if match:
            entities.location = ExtractedValue(
                value=match.group().strip(),
                confidence=0.8,
                source_text=match.group(),
            )

        # Intersection pattern
        if not entities.location:
            match = re.search(r'([\w\s]+)\s+(?:and|&)\s+([\w\s]+)', text, re.IGNORECASE)
            if match and any(
                word in match.group().lower()
                for word in ["street", "st", "avenue", "ave", "road", "rd"]
            ):
                entities.location = ExtractedValue(
                    value=match.group().strip(),
                    confidence=0.7,
                    source_text=match.group(),
                )

    def _extract_name(self, text: str, entities: ExtractedEntities):
        """Extract person name from text."""
        # Simple pattern for "First Last" or "First Middle Last"
        match = re.search(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', text)
        if match:
            entities.full_name = ExtractedValue(
                value=match.group().strip(),
                confidence=0.7,
                source_text=match.group(),
            )

    def _extract_loss_type(self, text_lower: str, entities: ExtractedEntities):
        """Extract loss type from text."""
        for loss_type, keywords in self.LOSS_TYPE_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                entities.loss_type = ExtractedValue(
                    value=loss_type,
                    confidence=0.85,
                    source_text=next(kw for kw in keywords if kw in text_lower),
                )
                return

    def _extract_injury_mention(self, text_lower: str, entities: ExtractedEntities):
        """Check for injury mentions."""
        injury_keywords = [
            "hurt", "injured", "injury", "pain", "hospital", "ambulance",
            "bleeding", "broken", "whiplash", "neck", "back", "head",
        ]
        for keyword in injury_keywords:
            if keyword in text_lower:
                entities.injury_mentioned = ExtractedValue(
                    value=True,
                    confidence=0.8,
                    source_text=keyword,
                )
                return

    def _extract_damage_areas(self, text_lower: str, entities: ExtractedEntities):
        """Extract damage areas mentioned."""
        for area, keywords in self.DAMAGE_AREAS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    entities.damage_areas.append(
                        ExtractedValue(
                            value=area,
                            confidence=0.75,
                            source_text=keyword,
                        )
                    )
                    break


# Singleton instance
_extraction_service: Optional[ExtractionService] = None


def get_extraction_service(use_llm: bool = False) -> ExtractionService:
    """Get or create extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService(use_llm=use_llm)
    return _extraction_service
