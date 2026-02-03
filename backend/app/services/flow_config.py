"""
Flow Configuration Service - Load and manage configurable document and intent flows.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models import DocumentFlowConfig, IntentConfig, FlowRule
from app.core.logging import logger


# Default document flows (used when no database config exists)
DEFAULT_DOCUMENT_FLOWS = {
    "auto": {
        "collision": ["police_report", "incident_photos", "repair_estimate", "invoice"],
        "theft": ["police_report", "incident_photos"],
        "vandalism": ["police_report", "incident_photos", "repair_estimate"],
        "default": ["incident_photos", "repair_estimate"],
    },
    "home": {
        "fire": ["incident_photos", "fire_department_report", "repair_estimate"],
        "water_damage": ["incident_photos", "repair_estimate"],
        "theft": ["police_report", "incident_photos"],
        "default": ["incident_photos", "repair_estimate"],
    },
    "medical": {
        "default": ["eob", "invoice"],
    },
}

# Default intents
DEFAULT_INTENTS = [
    {
        "name": "file_claim",
        "display_name": "File a New Claim",
        "icon": "📝",
        "applicable_products": ["auto", "home", "medical"],
    },
    {
        "name": "check_status",
        "display_name": "Check Claim Status",
        "icon": "🔍",
        "applicable_products": ["auto", "home", "medical"],
    },
    {
        "name": "coverage_question",
        "display_name": "Coverage Questions",
        "icon": "❓",
        "applicable_products": ["auto", "home", "medical"],
    },
    {
        "name": "billing",
        "display_name": "Billing Inquiry",
        "icon": "💵",
        "applicable_products": ["auto", "home", "medical"],
    },
]


def get_document_flow_config(
    db: Session,
    product_line: str,
    incident_type: Optional[str] = None,
) -> Optional[DocumentFlowConfig]:
    """
    Get the document flow configuration for a product line and incident type.

    Args:
        db: Database session
        product_line: Product line (auto, home, medical)
        incident_type: Optional incident type (collision, theft, fire, etc.)

    Returns:
        DocumentFlowConfig if found, else None
    """
    query = db.query(DocumentFlowConfig).filter(
        DocumentFlowConfig.product_line == product_line,
        DocumentFlowConfig.is_active == True,
    )

    if incident_type:
        # Try to find specific incident type config first
        specific = query.filter(
            DocumentFlowConfig.incident_type == incident_type
        ).order_by(DocumentFlowConfig.priority.desc()).first()

        if specific:
            return specific

    # Fall back to default (null incident_type) for this product
    return query.filter(
        DocumentFlowConfig.incident_type.is_(None)
    ).order_by(DocumentFlowConfig.priority.desc()).first()


def get_required_documents(
    db: Session,
    product_line: str,
    incident_type: Optional[str] = None,
) -> List[str]:
    """
    Get the list of required documents for a product line and incident type.

    Args:
        db: Database session
        product_line: Product line
        incident_type: Optional incident type

    Returns:
        List of document type names in order
    """
    config = get_document_flow_config(db, product_line, incident_type)

    if config:
        return config.document_sequence or []

    # Fall back to defaults
    product_flows = DEFAULT_DOCUMENT_FLOWS.get(product_line, {})
    if incident_type and incident_type in product_flows:
        return product_flows[incident_type]
    return product_flows.get("default", [])


def get_field_requirements(
    db: Session,
    product_line: str,
    incident_type: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Get field requirements for documents.

    Args:
        db: Database session
        product_line: Product line
        incident_type: Optional incident type
        doc_type: Optional specific document type

    Returns:
        Dict mapping doc_type to list of required field names
    """
    config = get_document_flow_config(db, product_line, incident_type)

    if config and config.field_requirements:
        if doc_type:
            return {doc_type: config.field_requirements.get(doc_type, [])}
        return config.field_requirements

    return {}


def evaluate_conditional_rules(
    db: Session,
    product_line: str,
    incident_type: Optional[str],
    collected_data: Dict[str, Any],
) -> List[str]:
    """
    Evaluate conditional rules to determine which documents are actually required.

    Args:
        db: Database session
        product_line: Product line
        incident_type: Incident type
        collected_data: Currently collected data (including document extractions)

    Returns:
        List of required document types after evaluating conditions
    """
    config = get_document_flow_config(db, product_line, incident_type)
    base_docs = get_required_documents(db, product_line, incident_type)

    if not config or not config.conditional_rules:
        return base_docs

    required_docs = []
    rules = config.conditional_rules

    for doc_type in base_docs:
        if doc_type not in rules:
            # No conditional rule, always required
            required_docs.append(doc_type)
            continue

        rule = rules[doc_type]
        required_if = rule.get("required_if")
        skip_if = rule.get("skip_if")

        # Evaluate skip_if first
        if skip_if and _evaluate_condition(skip_if, collected_data):
            logger.debug(f"Skipping {doc_type} due to skip_if condition")
            continue

        # Evaluate required_if
        if required_if:
            if _evaluate_condition(required_if, collected_data):
                required_docs.append(doc_type)
            else:
                logger.debug(f"Skipping {doc_type} - required_if condition not met")
        else:
            required_docs.append(doc_type)

    return required_docs


def _evaluate_condition(condition: str, data: Dict[str, Any]) -> bool:
    """
    Evaluate a simple condition string against data.

    Supports:
    - field_name == value
    - field_name != value
    - field_name (truthy check)
    - !field_name (falsy check)

    Args:
        condition: Condition string
        data: Data to evaluate against

    Returns:
        True if condition is met
    """
    condition = condition.strip()

    # Handle negation
    if condition.startswith("!"):
        field = condition[1:].strip()
        return not _get_nested_value(data, field)

    # Handle equality
    if "==" in condition:
        parts = condition.split("==")
        if len(parts) == 2:
            field = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            actual = _get_nested_value(data, field)
            return str(actual).lower() == expected.lower()

    # Handle inequality
    if "!=" in condition:
        parts = condition.split("!=")
        if len(parts) == 2:
            field = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            actual = _get_nested_value(data, field)
            return str(actual).lower() != expected.lower()

    # Truthy check
    return bool(_get_nested_value(data, condition))


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get a nested value from a dict using dot notation."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


# Intent Configuration Functions

def get_all_intents(db: Session, active_only: bool = True) -> List[IntentConfig]:
    """Get all intent configurations."""
    query = db.query(IntentConfig)
    if active_only:
        query = query.filter(IntentConfig.is_active == True)
    return query.order_by(IntentConfig.priority.desc()).all()


def get_intent_by_name(db: Session, name: str) -> Optional[IntentConfig]:
    """Get an intent by its name."""
    return db.query(IntentConfig).filter(IntentConfig.name == name).first()


def get_intents_for_product(db: Session, product_line: str) -> List[Dict[str, Any]]:
    """
    Get intents applicable to a product line.

    Args:
        db: Database session
        product_line: Product line

    Returns:
        List of intent dicts
    """
    intents = get_all_intents(db, active_only=True)

    if not intents:
        # Return defaults if no database config
        return [i for i in DEFAULT_INTENTS if product_line in i.get("applicable_products", [])]

    result = []
    for intent in intents:
        applicable = intent.applicable_products
        if applicable is None or product_line in applicable:
            result.append(intent.to_dict())

    return result


# Flow Rule Functions

def get_all_flow_rules(db: Session, active_only: bool = True) -> List[FlowRule]:
    """Get all flow rules."""
    query = db.query(FlowRule)
    if active_only:
        query = query.filter(FlowRule.is_active == True)
    return query.order_by(FlowRule.priority.desc()).all()


def evaluate_flow_rules(
    db: Session,
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Evaluate flow rules against a context and return the first matching action.

    Args:
        db: Database session
        context: Current state/context dict

    Returns:
        Action dict from the first matching rule, or None
    """
    rules = get_all_flow_rules(db, active_only=True)

    for rule in rules:
        if _evaluate_rule_conditions(rule.conditions, context):
            logger.info(f"Flow rule matched: {rule.name}")
            return rule.action

    return None


def _evaluate_rule_conditions(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Evaluate rule conditions against context.

    All conditions must match (AND logic).
    """
    for key, expected in conditions.items():
        actual = context.get(key)

        # Handle special condition types
        if key.endswith("_gt"):
            field = key[:-3]
            actual = context.get(field)
            if actual is None or float(actual) <= float(expected):
                return False
        elif key.endswith("_lt"):
            field = key[:-3]
            actual = context.get(field)
            if actual is None or float(actual) >= float(expected):
                return False
        elif key.endswith("_in"):
            field = key[:-3]
            actual = context.get(field)
            if actual not in expected:
                return False
        else:
            # Simple equality
            if actual != expected:
                return False

    return True


# CRUD Operations

def create_document_flow_config(
    db: Session,
    product_line: str,
    document_sequence: List[str],
    incident_type: Optional[str] = None,
    conditional_rules: Optional[Dict] = None,
    field_requirements: Optional[Dict] = None,
    created_by: Optional[str] = None,
) -> DocumentFlowConfig:
    """Create a new document flow configuration."""
    config = DocumentFlowConfig(
        product_line=product_line,
        incident_type=incident_type,
        document_sequence=document_sequence,
        conditional_rules=conditional_rules or {},
        field_requirements=field_requirements or {},
        created_by=created_by,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_document_flow_config(
    db: Session,
    config_id: str,
    updates: Dict[str, Any],
) -> Optional[DocumentFlowConfig]:
    """Update a document flow configuration."""
    config = db.query(DocumentFlowConfig).filter(
        DocumentFlowConfig.config_id == config_id
    ).first()

    if not config:
        return None

    for key, value in updates.items():
        if hasattr(config, key):
            setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config


def delete_document_flow_config(db: Session, config_id: str) -> bool:
    """Delete a document flow configuration."""
    config = db.query(DocumentFlowConfig).filter(
        DocumentFlowConfig.config_id == config_id
    ).first()

    if not config:
        return False

    db.delete(config)
    db.commit()
    return True


def create_intent_config(
    db: Session,
    name: str,
    display_name: str,
    description: Optional[str] = None,
    applicable_products: Optional[List[str]] = None,
    trigger_phrases: Optional[List[str]] = None,
    required_fields: Optional[List[str]] = None,
    flow_config: Optional[Dict] = None,
    icon: Optional[str] = None,
) -> IntentConfig:
    """Create a new intent configuration."""
    intent = IntentConfig(
        name=name,
        display_name=display_name,
        description=description,
        applicable_products=applicable_products,
        trigger_phrases=trigger_phrases or [],
        required_fields=required_fields or [],
        flow_config=flow_config or {},
        icon=icon,
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent


def update_intent_config(
    db: Session,
    intent_id: str,
    updates: Dict[str, Any],
) -> Optional[IntentConfig]:
    """Update an intent configuration."""
    intent = db.query(IntentConfig).filter(
        IntentConfig.intent_id == intent_id
    ).first()

    if not intent:
        return None

    for key, value in updates.items():
        if hasattr(intent, key):
            setattr(intent, key, value)

    db.commit()
    db.refresh(intent)
    return intent


def delete_intent_config(db: Session, intent_id: str) -> bool:
    """Delete an intent configuration."""
    intent = db.query(IntentConfig).filter(
        IntentConfig.intent_id == intent_id
    ).first()

    if not intent:
        return False

    db.delete(intent)
    db.commit()
    return True


def create_flow_rule(
    db: Session,
    name: str,
    conditions: Dict[str, Any],
    action: Dict[str, Any],
    description: Optional[str] = None,
    priority: int = 0,
) -> FlowRule:
    """Create a new flow rule."""
    rule = FlowRule(
        name=name,
        description=description,
        conditions=conditions,
        action=action,
        priority=priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_flow_rule(
    db: Session,
    rule_id: str,
    updates: Dict[str, Any],
) -> Optional[FlowRule]:
    """Update a flow rule."""
    rule = db.query(FlowRule).filter(FlowRule.rule_id == rule_id).first()

    if not rule:
        return None

    for key, value in updates.items():
        if hasattr(rule, key):
            setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return rule


def delete_flow_rule(db: Session, rule_id: str) -> bool:
    """Delete a flow rule."""
    rule = db.query(FlowRule).filter(FlowRule.rule_id == rule_id).first()

    if not rule:
        return False

    db.delete(rule)
    db.commit()
    return True
