"""
Synthetic Data Generator - Seed Script
Generates realistic demo data for policies, users, claims, and providers.
"""
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List
import uuid

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import (
    User, AuthLevel, UserRole,
    Policy, PolicyCoverage, ProductType, PolicyStatus,
    Claim, ClaimType, ClaimStatus,
    Provider, NetworkStatus,
    SystemSettings,
)
from app.core import hash_password

# Seed for reproducibility
random.seed(42)


# Sample data
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Dorothy", "Paul", "Kimberly", "Andrew", "Emily", "Joshua", "Donna",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
]

CITIES = [
    ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"), ("Chicago", "IL", "60601"),
    ("Houston", "TX", "77001"), ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"), ("Dallas", "TX", "75201"),
    ("San Jose", "CA", "95101"),
]

SPECIALTIES = [
    "Family Medicine", "Internal Medicine", "Pediatrics", "Cardiology", "Orthopedics",
    "Dermatology", "Gastroenterology", "Neurology", "Oncology", "Psychiatry",
]


def generate_users(db: Session, count: int = 50) -> List[User]:
    """Generate synthetic users."""
    users = []
    
    # Create admin user
    admin = User(
        email="admin@claimbot.demo",
        password_hash=hash_password("admin123"),
        name="System Admin",
        auth_level=AuthLevel.AUTH,
        role=UserRole.ADMIN,
    )
    db.add(admin)
    users.append(admin)
    
    # Create Celest user
    celest = User(
        email="celest@claimbot.demo",
        password_hash=hash_password("celest123"),
        name="Claims Specialist",
        auth_level=AuthLevel.AUTH,
        role=UserRole.CELEST,
    )
    db.add(celest)
    users.append(celest)
    
    # Create customer users
    for i in range(count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@example.com"
        
        user = User(
            email=email,
            password_hash=hash_password("demo123"),
            name=f"{first} {last}",
            auth_level=AuthLevel.AUTH,
            role=UserRole.CUSTOMER,
        )
        db.add(user)
        users.append(user)
    
    db.commit()
    return users


def generate_policies(db: Session, users: List[User]) -> List[Policy]:
    """Generate synthetic policies for users."""
    policies = []
    customers = [u for u in users if u.role == UserRole.CUSTOMER]
    
    for user in customers:
        # Each user gets 1-3 policies
        num_policies = random.randint(1, 3)
        product_types = random.sample(list(ProductType), min(num_policies, 3))
        
        for product_type in product_types:
            policy_number = f"{product_type.value[:3].upper()}-{random.randint(100000, 999999)}"
            effective = date.today() - timedelta(days=random.randint(30, 365))
            
            policy = Policy(
                policy_number=policy_number,
                user_id=user.user_id,
                product_type=product_type,
                effective_date=effective,
                expiration_date=effective + timedelta(days=365),
                status=PolicyStatus.ACTIVE,
            )
            db.add(policy)
            db.flush()  # Get policy_id
            
            # Add coverages based on product type
            if product_type == ProductType.AUTO:
                coverages = [
                    ("collision", Decimal("50000"), Decimal("500")),
                    ("comprehensive", Decimal("50000"), Decimal("250")),
                    ("liability", Decimal("100000"), Decimal("0")),
                ]
            elif product_type == ProductType.HOME:
                coverages = [
                    ("dwelling", Decimal("300000"), Decimal("1000")),
                    ("personal_property", Decimal("100000"), Decimal("500")),
                    ("liability", Decimal("300000"), Decimal("0")),
                ]
            else:  # MEDICAL
                coverages = [
                    ("hospital", Decimal("1000000"), Decimal("2500"), Decimal("250"), Decimal("20")),
                    ("physician", Decimal("500000"), Decimal("2500"), Decimal("40"), Decimal("20")),
                    ("prescription", Decimal("50000"), Decimal("0"), Decimal("15"), Decimal("0")),
                ]
            
            for cov in coverages:
                if len(cov) == 3:
                    coverage = PolicyCoverage(
                        policy_id=policy.policy_id,
                        coverage_type=cov[0],
                        limit_amount=cov[1],
                        deductible=cov[2],
                    )
                else:
                    coverage = PolicyCoverage(
                        policy_id=policy.policy_id,
                        coverage_type=cov[0],
                        limit_amount=cov[1],
                        deductible=cov[2],
                        copay=cov[3],
                        coinsurance_pct=cov[4],
                    )
                db.add(coverage)
            
            policies.append(policy)
    
    db.commit()
    return policies


def generate_claims(db: Session, policies: List[Policy], count: int = 30) -> List[Claim]:
    """Generate synthetic claims."""
    claims = []
    
    for _ in range(count):
        policy = random.choice(policies)
        claim_type = ClaimType.MEDICAL if policy.product_type == ProductType.MEDICAL else ClaimType.INCIDENT
        
        # Random past date
        incident_date = date.today() - timedelta(days=random.randint(1, 180))
        
        # Generate metadata based on type
        if claim_type == ClaimType.INCIDENT:
            metadata = {
                "location": f"{random.choice(CITIES)[0]}, {random.choice(CITIES)[1]}",
                "description": random.choice([
                    "Rear-end collision at traffic light",
                    "Storm damage to roof",
                    "Theft of personal property",
                    "Water damage from pipe burst",
                    "Deer collision on highway",
                ]),
            }
            loss_amount = Decimal(str(random.randint(500, 25000)))
        else:
            metadata = {
                "provider_npi": f"{random.randint(1000000000, 9999999999)}",
                "diagnosis_codes": [f"Z{random.randint(10, 99)}.{random.randint(0, 9)}"],
                "procedure_codes": [f"99{random.randint(201, 215)}"],
            }
            loss_amount = Decimal(str(random.randint(100, 5000)))
        
        claim = Claim(
            policy_id=policy.policy_id,
            claim_number=f"CLM-{uuid.uuid4().hex[:8].upper()}",
            claim_type=claim_type,
            status=random.choice(list(ClaimStatus)),
            incident_date=incident_date,
            loss_amount=loss_amount,
            metadata=metadata,
            timeline=[{
                "status": "created",
                "timestamp": datetime.utcnow().isoformat(),
                "actor": "system",
                "notes": "Claim generated for demo",
            }],
        )
        db.add(claim)
        claims.append(claim)
    
    db.commit()
    return claims


def generate_providers(db: Session, count: int = 20) -> List[Provider]:
    """Generate synthetic medical providers."""
    providers = []
    
    for i in range(count):
        city, state, zip_code = random.choice(CITIES)
        specialty = random.choice(SPECIALTIES)
        
        # Random NPI (10 digits)
        npi = f"{random.randint(1000000000, 9999999999)}"
        
        # Allowed amounts for common procedure codes
        allowed_amounts = {
            "99201": round(random.uniform(50, 80), 2),
            "99202": round(random.uniform(80, 120), 2),
            "99203": round(random.uniform(100, 150), 2),
            "99204": round(random.uniform(150, 200), 2),
            "99205": round(random.uniform(200, 280), 2),
            "99211": round(random.uniform(25, 40), 2),
            "99212": round(random.uniform(50, 75), 2),
            "99213": round(random.uniform(80, 120), 2),
            "99214": round(random.uniform(120, 180), 2),
            "99215": round(random.uniform(180, 250), 2),
        }
        
        provider = Provider(
            npi=npi,
            name=f"Dr. {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            specialties=[specialty],
            network_status=random.choice([NetworkStatus.IN_NETWORK, NetworkStatus.IN_NETWORK, NetworkStatus.OUT_OF_NETWORK]),
            allowed_amounts=allowed_amounts,
            address=f"{random.randint(100, 999)} Main St",
            city=city,
            state=state,
            zip_code=zip_code,
        )
        db.add(provider)
        providers.append(provider)
    
    db.commit()
    return providers


def seed_default_settings(db: Session) -> None:
    """Seed default system settings."""
    defaults = [
        ("llm_provider", "ollama", "Active LLM provider"),
        ("ollama_model", "llama3", "Ollama model name"),
        ("ollama_vision_model", "llava", "Ollama vision model name"),
        ("ollama_endpoint", "http://localhost:11434", "Ollama endpoint URL"),
        ("bedrock_model", "anthropic.claude-3-sonnet-20240229-v1:0", "Bedrock model ID"),
        ("confidence_threshold", 0.7, "AI confidence threshold for escalation"),
        ("auto_approval_limit", 5000.0, "Maximum amount for auto-approval"),
    ]
    
    for key, value, desc in defaults:
        existing = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if not existing:
            setting = SystemSettings(key=key, value=value, description=desc)
            db.add(setting)
    
    db.commit()


def run_seed():
    """Run the complete seed process."""
    print("Starting database seed...")
    
    db = SessionLocal()
    try:
        # Generate data
        print("Generating users...")
        users = generate_users(db, count=50)
        print(f"  Created {len(users)} users")
        
        print("Generating policies...")
        policies = generate_policies(db, users)
        print(f"  Created {len(policies)} policies")
        
        print("Generating claims...")
        claims = generate_claims(db, policies, count=30)
        print(f"  Created {len(claims)} claims")
        
        print("Generating providers...")
        providers = generate_providers(db, count=20)
        print(f"  Created {len(providers)} providers")
        
        print("Seeding default settings...")
        seed_default_settings(db)
        
        print("\n✅ Database seeded successfully!")
        print("\nDemo credentials:")
        print("  Admin: admin@claimbot.demo / admin123")
        print("  Celest: celest@claimbot.demo / celest123")
        print("  Customer: any generated user / demo123")
        
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
