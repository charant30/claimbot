"""
Fresh Database Start

Completely drops all tables, recreates them, and seeds with:
- Admin user
- Celest user  
- ONE complete customer with full policy, vehicles, drivers, coverages, and claims
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.db.models import (
    User, AuthLevel, UserRole,
    Policy, PolicyCoverage, PolicyVehicle, PolicyDriver, ProductType, PolicyStatus,
    Claim, ClaimType, ClaimStatus,
    SystemSettings,
)
from app.db.models.policy import DriverRelationship
from app.core import hash_password


def drop_all_tables():
    """Drop all tables in the database."""
    print("\n1. Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("   > All tables dropped")


def create_all_tables():
    """Create all tables from models."""
    print("\n2. Creating fresh tables...")
    Base.metadata.create_all(bind=engine)
    print("   > All tables created")


def seed_system_settings(db: Session):
    """Seed default system settings."""
    print("\n3. Seeding system settings...")
    defaults = [
        ("llm_provider", "openai", "Active LLM provider"),
        ("openai_model", "gpt-4o-mini", "OpenAI model name"),
        ("openai_vision_model", "gpt-4o-mini", "OpenAI vision model name"),
        ("ollama_model", "llama3", "Ollama model name"),
        ("ollama_vision_model", "llava", "Ollama vision model name"),
        ("ollama_endpoint", "http://localhost:11434", "Ollama endpoint URL"),
        ("bedrock_model", "anthropic.claude-3-sonnet-20240229-v1:0", "Bedrock model ID"),
        ("confidence_threshold", 0.7, "AI confidence threshold for escalation"),
        ("auto_approval_limit", 5000.0, "Maximum amount for auto-approval"),
    ]
    
    for key, value, desc in defaults:
        setting = SystemSettings(key=key, value=value, description=desc)
        db.add(setting)
    
    db.commit()
    print("   > System settings seeded")


def create_admin_users(db: Session):
    """Create admin and celest users."""
    print("\n4. Creating admin users...")
    
    # Admin
    admin = User(
        email="admin@claimbot.demo",
        password_hash=hash_password("admin123"),
        name="System Admin",
        auth_level=AuthLevel.AUTH,
        role=UserRole.ADMIN,
    )
    db.add(admin)
    print("   > Created admin: admin@claimbot.demo")
    
    # Celest
    celest = User(
        email="celest@claimbot.demo",
        password_hash=hash_password("celest123"),
        name="Claims Specialist",
        auth_level=AuthLevel.AUTH,
        role=UserRole.CELEST,
    )
    db.add(celest)
    print("   > Created celest: celest@claimbot.demo")
    
    db.commit()


def create_complete_customer(db: Session):
    """Create ONE complete customer with all details."""
    print("\n5. Creating complete customer with policy, vehicles, drivers, and claims...")
    
    # Customer user
    customer = User(
        email="john.smith@example.com",
        password_hash=hash_password("demo123"),
        name="John Smith",
        auth_level=AuthLevel.AUTH,
        role=UserRole.CUSTOMER,
    )
    db.add(customer)
    db.flush()
    print(f"   > Customer: {customer.name} ({customer.email})")
    
    # Policy dates and personal info (current year for active policy)
    today = date.today()
    # Policy started 30 days ago and expires in 330 days (active for ~1 year total)
    policy_effective = today - timedelta(days=30)
    policy_expiration = today + timedelta(days=330)
    customer_dob = date(1985, 6, 15)
    
    # Auto policy with complete holder information
    policy = Policy(
        policy_number="AUTO-123456",
        user_id=customer.user_id,
        product_type=ProductType.AUTO,
        effective_date=policy_effective,
        expiration_date=policy_expiration,
        status=PolicyStatus.ACTIVE,
        # Complete holder details (required for FNOL identity matching)
        holder_first_name="John",
        holder_last_name="Smith",
        holder_phone="555-123-4567",
        holder_email=customer.email,
        holder_dob=customer_dob,
        holder_address="123 Main Street, Apt 4B",
        holder_zip="10001",
    )
    db.add(policy)
    db.flush()
    print(f"   > Policy: {policy.policy_number}")
    
    # Coverages (standard auto coverages)
    coverages_data = [
        ("collision", Decimal("50000"), Decimal("500")),
        ("comprehensive", Decimal("50000"), Decimal("250")),
        ("liability", Decimal("100000"), Decimal("0")),
        ("uninsured_motorist", Decimal("100000"), Decimal("0")),
        ("personal_injury_protection", Decimal("10000"), Decimal("0")),
    ]
    
    for cov_type, limit, deductible in coverages_data:
        coverage = PolicyCoverage(
            policy_id=policy.policy_id,
            coverage_type=cov_type,
            limit_amount=limit,
            deductible=deductible,
        )
        db.add(coverage)
    print(f"   > Coverages: {len(coverages_data)} types")
    
    # Vehicle 1: Primary vehicle (complete details)
    vehicle1 = PolicyVehicle(
        policy_id=policy.policy_id,
        vin="1HGCM82633A123456",
        year=2023,
        make="Honda",
        model="Accord",
        body_type="sedan",
        color="Silver",
        license_plate="ABC1234",
        license_state="NY",
        ownership_status="owned",
        annual_mileage=12000,
        primary_use="commute",
        is_active=True,
    )
    db.add(vehicle1)
    print(f"   > Vehicle 1: {vehicle1.year} {vehicle1.make} {vehicle1.model} ({vehicle1.vin})")
    
    # Vehicle 2: Second vehicle
    vehicle2 = PolicyVehicle(
        policy_id=policy.policy_id,
        vin="5TDJKRFH3ES123789",
        year=2021,
        make="Toyota",
        model="Highlander",
        body_type="suv",
        color="Blue",
        license_plate="XYZ5678",
        license_state="NY",
        ownership_status="financed",
        annual_mileage=10000,
        primary_use="pleasure",
        is_active=True,
    )
    db.add(vehicle2)
    print(f"   > Vehicle 2: {vehicle2.year} {vehicle2.make} {vehicle2.model} ({vehicle2.vin})")
    
    # Primary driver (policyholder - complete license info)
    driver1 = PolicyDriver(
        policy_id=policy.policy_id,
        first_name="John",
        last_name="Smith",
        date_of_birth=customer_dob,
        gender="male",
        license_number="N123456789",
        license_state="NY",
        license_status="valid",
        license_expiration=date(2028, 6, 15),
        driver_relationship=DriverRelationship.SELF,
        is_primary=True,
        years_licensed=23,
        accidents_3yr=0,
        violations_3yr=0,
        is_active=True,
        is_excluded=False,
    )
    db.add(driver1)
    print(f"   > Driver 1: {driver1.first_name} {driver1.last_name} (Primary, License: {driver1.license_number})")
    
    # Secondary driver (spouse)
    driver2 = PolicyDriver(
        policy_id=policy.policy_id,
        first_name="Sarah",
        last_name="Smith",
        date_of_birth=date(1987, 3, 22),
        gender="female",
        license_number="N987654321",
        license_state="NY",
        license_status="valid",
        license_expiration=date(2027, 3, 22),
        driver_relationship=DriverRelationship.SPOUSE,
        is_primary=False,
        years_licensed=20,
        accidents_3yr=0,
        violations_3yr=1,
        is_active=True,
        is_excluded=False,
    )
    db.add(driver2)
    print(f"   > Driver 2: {driver2.first_name} {driver2.last_name} (Spouse, License: {driver2.license_number})")
    
    # Sample Claim 1 (submitted recently)
    claim1 = Claim(
        policy_id=policy.policy_id,
        claim_number="INC-2024-001234",
        claim_type=ClaimType.INCIDENT,
        status=ClaimStatus.SUBMITTED,
        incident_date=today - timedelta(days=5),  # 5 days ago
        loss_amount=Decimal("3500.00"),
        claim_metadata={
            "description": "Rear-ended at red light on Broadway",
            "location": "Broadway & 42nd St, New York, NY",
            "loss_type": "collision",
            "vehicles": [{
                "vehicle_id": "insured_vehicle_1",
                "role": "insured",
                "vin": vehicle1.vin,
                "make": vehicle1.make,
                "model": vehicle1.model,
                "year": vehicle1.year,
            }],
            "parties": [{
                "party_id": "party_1",
                "role": "insured_driver",
                "first_name": "John",
                "last_name": "Smith",
            }],
            "injuries": [],
            "damages": [{
                "damage_id": "damage_1",
                "damage_type": "vehicle",
                "damage_area": "rear_bumper",
                "description": "Rear bumper dented, taillight cracked",
                "estimated_amount": 3500.00,
            }],
        },
        timeline=[{
            "status": "submitted",
            "timestamp": datetime.utcnow().isoformat(),
            "actor": "customer",
            "notes": "Claim submitted via FNOL",
        }],
    )
    db.add(claim1)
    print(f"   > Claim 1: {claim1.claim_number} (${claim1.loss_amount})")
    
    # Sample Claim 2 (under review)
    claim2 = Claim(
        policy_id=policy.policy_id,
        claim_number="INC-2024-002345",
        claim_type=ClaimType.INCIDENT,
        status=ClaimStatus.UNDER_REVIEW,
        incident_date=today - timedelta(days=15),  # 15 days ago
        loss_amount=Decimal("7200.00"),
        claim_metadata={
            "description": "Collision with deer on highway",
            "location": "I-87 North, near Exit 15",
            "loss_type": "collision",
        },
        timeline=[
            {
                "status": "submitted",
                "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                "actor": "customer",
                "notes": "Claim submitted",
            },
            {
                "status": "under_review",
                "timestamp": (datetime.utcnow() - timedelta(days=8)).isoformat(),
                "actor": "adjuster",
                "notes": "Assigned to adjuster for review",
            },
        ],
    )
    db.add(claim2)
    print(f"   > Claim 2: {claim2.claim_number} (${claim2.loss_amount})")
    
    db.commit()


def fresh_start():
    """Execute fresh database setup."""
    print("="*70)
    print("FRESH DATABASE START")
    print("="*70)
    print(f"\nDatabase: {settings.DATABASE_URL.split('@')[-1]}")
    
    try:
        # Drop and recreate tables
        drop_all_tables()
        create_all_tables()
        
        # Create session for seeding
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        try:
            # Seed data
            seed_system_settings(db)
            create_admin_users(db)
            create_complete_customer(db)
            
            print("\n" + "="*70)
            print("SUCCESS! Database is ready")
            print("="*70)
            print("\nLOGIN CREDENTIALS:")
            print("-" * 70)
            # Get the created data for display
            policy = db.query(Policy).filter(Policy.policy_number == "AUT-123456").first()
            
            # Get the created data for display
            policy = db.query(Policy).filter(Policy.policy_number == "AUTO-123456").first()
            
            print("CUSTOMER (Main Test Account):")
            print("  Email:    john.smith@example.com")
            print("  Password: demo123")
            print("  Policy:   AUTO-123456")
            if policy:
                print(f"  Status:   ACTIVE ({policy.effective_date} to {policy.expiration_date})")
            print("  Vehicles: 2023 Honda Accord, 2021 Toyota Highlander")
            print("  Drivers:  John Smith (Primary), Sarah Smith (Spouse)")
            print("  Claims:   INC-2024-001234, INC-2024-002345")
            print()
            print("ADMIN:")
            print("  Email:    admin@claimbot.demo")
            print("  Password: admin123")
            print()
            print("CELEST (Claims Specialist):")
            print("  Email:    celest@claimbot.demo")
            print("  Password: celest123")
            print("="*70)
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    fresh_start()
