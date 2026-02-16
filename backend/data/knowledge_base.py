"""
Insurance Knowledge Base - Coverage explanations, FAQs, and billing info
for the inquiry agent to use when answering customer questions.
"""

COVERAGE_EXPLANATIONS = {
    "collision": {
        "name": "Collision Coverage",
        "description": "Covers damage to your vehicle resulting from a collision with another vehicle or object (e.g., tree, guardrail, pole), regardless of who is at fault.",
        "what_it_covers": [
            "Damage to your car from hitting another vehicle",
            "Damage from hitting a stationary object (pole, guardrail, tree)",
            "Single-vehicle accidents (e.g., rolling your car)",
        ],
        "what_it_does_not_cover": [
            "Damage to the other party's vehicle (covered by liability)",
            "Theft or vandalism (covered by comprehensive)",
            "Medical expenses (covered by PIP or medical payments)",
        ],
        "how_deductible_works": "You pay the deductible amount first, then insurance covers the rest up to your coverage limit. For example, if your deductible is $500 and repairs cost $3,000, you pay $500 and insurance pays $2,500.",
    },
    "comprehensive": {
        "name": "Comprehensive Coverage",
        "description": "Covers damage to your vehicle from non-collision events such as theft, vandalism, natural disasters, falling objects, and animal strikes.",
        "what_it_covers": [
            "Theft of your vehicle",
            "Vandalism",
            "Natural disasters (hail, flood, earthquake, tornado)",
            "Falling objects (tree branches, debris)",
            "Animal strikes (deer, etc.)",
            "Fire damage",
            "Broken windshield or glass",
        ],
        "what_it_does_not_cover": [
            "Collision damage (covered by collision coverage)",
            "Personal belongings inside the car",
            "Mechanical breakdown or wear and tear",
        ],
        "how_deductible_works": "Similar to collision - you pay the deductible, insurance covers the rest up to your limit.",
    },
    "liability": {
        "name": "Liability Coverage",
        "description": "Covers damage and injuries you cause to other people and their property in an accident where you are at fault. This is required by law in most states.",
        "what_it_covers": [
            "Bodily injury to others (medical bills, lost wages, pain and suffering)",
            "Property damage to others (vehicle repair, damaged property)",
            "Legal defense costs if you are sued",
        ],
        "what_it_does_not_cover": [
            "Your own injuries (covered by PIP)",
            "Your own vehicle damage (covered by collision/comprehensive)",
            "Intentional acts",
        ],
        "how_deductible_works": "Liability coverage typically does not have a deductible. Your insurer pays for covered claims up to your policy limit.",
    },
    "uninsured_motorist": {
        "name": "Uninsured/Underinsured Motorist Coverage",
        "description": "Protects you if you are in an accident caused by a driver who has no insurance or insufficient insurance to cover your damages.",
        "what_it_covers": [
            "Your medical bills if hit by an uninsured driver",
            "Lost wages from an accident with an uninsured driver",
            "Vehicle damage (in some states)",
            "Hit-and-run accidents",
        ],
        "what_it_does_not_cover": [
            "Accidents where you are at fault",
            "Damage to the uninsured driver's vehicle",
        ],
        "how_deductible_works": "May have a deductible depending on your state and policy.",
    },
    "personal_injury_protection": {
        "name": "Personal Injury Protection (PIP)",
        "description": "Covers medical expenses, lost wages, and other costs for you and your passengers after an accident, regardless of who is at fault.",
        "what_it_covers": [
            "Medical and surgical expenses",
            "Lost wages and income replacement",
            "Funeral expenses",
            "Rehabilitation costs",
            "Essential services (childcare, housekeeping if you are injured)",
        ],
        "what_it_does_not_cover": [
            "Vehicle damage",
            "Non-accident related medical expenses",
        ],
        "how_deductible_works": "PIP may have a deductible. Once met, your insurer covers costs up to your PIP limit.",
    },
    "rental_reimbursement": {
        "name": "Rental Reimbursement Coverage",
        "description": "Pays for a rental car while your vehicle is being repaired after a covered claim.",
        "what_it_covers": [
            "Rental car costs while your vehicle is in the shop for a covered repair",
            "Alternative transportation costs",
        ],
        "what_it_does_not_cover": [
            "Rental costs for mechanical breakdown",
            "Costs exceeding your daily limit or max days",
        ],
        "how_deductible_works": "Coverage pays up to a daily limit for a maximum number of days specified in your policy.",
    },
}


CLAIMS_FAQ = {
    "how_to_file": "To file a claim, select 'File a New Claim' from the main menu. You will be guided through a step-by-step process to provide incident details, vehicle information, and supporting evidence.",
    "claim_timeline": "Most claims are processed within 7-14 business days. Simple claims may be resolved faster, while complex claims involving injuries or disputes may take longer.",
    "claim_statuses": {
        "draft": "Your claim has been started but not yet submitted.",
        "submitted": "Your claim has been submitted and is awaiting initial review.",
        "under_review": "An adjuster is reviewing your claim details and evidence.",
        "approved": "Your claim has been approved. Payment processing will begin shortly.",
        "denied": "Your claim has been denied. You will receive a detailed explanation and can appeal the decision.",
        "paid": "Payment has been issued for your claim.",
    },
    "what_to_do_after_accident": [
        "Ensure everyone is safe and call 911 if there are injuries",
        "Move to a safe location if possible",
        "Exchange information with other parties involved",
        "Take photos of the damage, scene, and any relevant details",
        "File a police report if required",
        "Contact your insurance company to file a claim",
    ],
    "documents_needed": [
        "Photos of the damage",
        "Police report (if applicable)",
        "Other party's insurance information",
        "Medical records (if injuries are involved)",
        "Repair estimates",
    ],
}


BILLING_FAQ = {
    "payment_methods": "We accept credit cards, debit cards, and bank account (ACH) transfers. You can update your payment method through your account settings or by contacting customer service.",
    "when_is_payment_due": "Your premium is due on your billing date each month. If you have annual billing, the full amount is due on your policy renewal date.",
    "late_payment": "If your payment is late, you have a 10-day grace period. During this time, your coverage remains active. After the grace period, your policy may be subject to cancellation.",
    "how_premium_is_calculated": "Your premium is based on factors including your driving record, vehicle type, location, coverage levels, deductibles, and any applicable discounts.",
    "discounts_available": [
        "Multi-vehicle discount",
        "Good driver discount (no accidents or violations in 3+ years)",
        "Bundling discount (multiple policy types)",
        "Paperless billing discount",
        "Pay-in-full discount",
    ],
    "how_to_reduce_premium": [
        "Increase your deductibles",
        "Maintain a clean driving record",
        "Bundle multiple policies",
        "Ask about available discounts",
        "Review your coverage levels annually",
    ],
}


GENERAL_FAQ = {
    "what_is_deductible": "A deductible is the amount you pay out of pocket before your insurance coverage kicks in. For example, if you have a $500 deductible and $3,000 in damage, you pay $500 and your insurance pays $2,500.",
    "what_is_premium": "A premium is the amount you pay for your insurance policy, usually on a monthly or annual basis. It is the cost of having insurance coverage.",
    "what_is_coverage_limit": "A coverage limit is the maximum amount your insurance will pay for a covered claim. For example, if your liability limit is $100,000, your insurer will pay up to that amount for claims against you.",
    "difference_collision_comprehensive": "Collision covers damage from hitting another vehicle or object. Comprehensive covers non-collision events like theft, vandalism, weather damage, and animal strikes.",
    "when_to_file_claim": "File a claim when you have damage or losses that exceed your deductible. If damage is minor and costs less than your deductible, it may not be worth filing.",
    "will_claim_raise_premium": "Filing a claim may affect your premium at renewal, especially if you are found at fault. However, comprehensive claims (weather, theft) typically have less impact than at-fault collision claims.",
}


def get_full_knowledge_base() -> str:
    """Get the complete knowledge base as a formatted string for LLM context."""
    sections = []
    
    sections.append("=== COVERAGE TYPES ===")
    for cov_type, info in COVERAGE_EXPLANATIONS.items():
        sections.append(f"\n{info['name']} ({cov_type}):")
        sections.append(f"  Description: {info['description']}")
        sections.append(f"  Deductible: {info['how_deductible_works']}")
    
    sections.append("\n=== CLAIM STATUSES ===")
    for status, desc in CLAIMS_FAQ["claim_statuses"].items():
        sections.append(f"  {status}: {desc}")
    
    sections.append(f"\n=== CLAIM TIMELINE ===\n  {CLAIMS_FAQ['claim_timeline']}")
    
    sections.append("\n=== BILLING FAQ ===")
    sections.append(f"  Payment methods: {BILLING_FAQ['payment_methods']}")
    sections.append(f"  Late payment: {BILLING_FAQ['late_payment']}")
    sections.append(f"  Premium calculation: {BILLING_FAQ['how_premium_is_calculated']}")
    
    sections.append("\n=== GENERAL FAQ ===")
    for key, value in GENERAL_FAQ.items():
        label = key.replace("_", " ").title()
        sections.append(f"  {label}: {value}")
    
    return "\n".join(sections)
