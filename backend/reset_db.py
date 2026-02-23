"""
Complete Database Reset - Drop all tables and recreate with one customer

This script:
1. Drops all tables
2. Recreates schema
3. Seeds with ONE complete customer with full data
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.db.models import (
    User, AuthLevel, UserRole,
    Policy, PolicyCoverage, PolicyVehicle, PolicyDriver, ProductType, PolicyStatus,
    Claim, ClaimType, ClaimStatus,
    SystemSettings,
)
from app.db.models.policy import DriverRelationship
from app.core import hash_password


def reset_database():
    """Drop all tables, recreate schema, and seed with one customer."""
    print("="*70)
    print("DATABASE RESET - Drop all tables and recreate")
    print("="*70)
    
    db = SessionLocal()
    try:
        # Step 1: Drop all tables
        print("\n[1/3] Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("      All tables dropped")
        
        # Step 2: Recreate all tables
        print("\n[2/3] Creating fresh schema...")
        Base.metadata.create_all(bind=engine)
        print("      Schema created")
        
        # Step 3: Seed with essential data
        print("\n[3/3] Seeding database...")
        
        # Admin user
        admin = User(
            email="admin@claimbot.demo",
            password_hash=hash_password("admin123"),
            name="System Admin",
            auth_level=AuthLevel.AUTH,
            role=UserRole.ADMIN,
        )
        db.add(admin)
        print("      > Admin user created")
        
        # Celest user
        celest = User(
            email="celest@claimbot.demo",
            password_hash=hash_password("celest123"),
            name="Claims Specialist",
            auth_level=AuthLevel.AUTH,
            role=UserRole.CELEST,
        )
        db.add(celest)
        print("      > Celest user created")
        
        # ONE Customer with complete details
        customer = User(
            email="john.smith@example.com",
            password_hash=hash_password("demo123"),
            name="John Smith",
            auth_level=AuthLevel.AUTH,
            role=UserRole.CUSTOMER,
        )
        db.add(customer)
        db.flush()
        print("      > Customer user created: John Smith")
        
        # Policy with complete holder details
        customer_dob = date(1985, 6, 15)
        policy = Policy(
            policy_number="AUTO-123456",
            user_id=customer.user_id,
            product_type=ProductType.AUTO,
            effective_date=date(2024, 1, 1),
            expiration_date=date(2025, 1, 1),
            status=PolicyStatus.ACTIVE,
            holder_first_name="John",
            holder_last_name="Smith",
            holder_phone="555-123-4567",
            holder_email=customer.email,
            holder_dob=customer_dob,
            holder_address="123 Main Street, Apt 4B",
            holder_zip="10001",
            # Billing information
            premium_monthly=Decimal("125.00"),
            premium_annual=Decimal("1425.00"),
            payment_method="credit_card",
            next_payment_date=date(2026, 3, 1),
            payment_status="current",
        )
        db.add(policy)
        db.flush()
        print("      > Policy created: AUTO-123456")
        
        # Coverages
        coverages = [
            ("collision", Decimal("50000"), Decimal("500")),
            ("comprehensive", Decimal("50000"), Decimal("250")),
            ("liability", Decimal("100000"), Decimal("0")),
            ("uninsured_motorist", Decimal("100000"), Decimal("0")),
            ("personal_injury_protection", Decimal("10000"), Decimal("0")),
        ]
        for cov_type, limit, deductible in coverages:
            db.add(PolicyCoverage(
                policy_id=policy.policy_id,
                coverage_type=cov_type,
                limit_amount=limit,
                deductible=deductible,
            ))
        print(f"      > Added {len(coverages)} coverages")
        
        # Vehicles
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
        print("      > Added 2 vehicles (Honda Accord, Toyota Highlander)")
        
        # Drivers
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
        print("      > Added 2 drivers (John-Primary, Sarah-Spouse)")
        
        # Sample claims
        claim1 = Claim(
            policy_id=policy.policy_id,
            claim_number="INC-2024-001234",
            claim_type=ClaimType.INCIDENT,
            status=ClaimStatus.SUBMITTED,
            incident_date=date(2024, 11, 15),
            loss_amount=Decimal("3500.00"),
            claim_metadata={
                "description": "Rear-ended at red light on Broadway",
                "location": "Broadway & 42nd St, New York, NY",
                "loss_type": "collision",
            },
            timeline=[{
                "status": "submitted",
                "timestamp": datetime.utcnow().isoformat(),
                "actor": "customer",
                "notes": "Claim submitted via FNOL",
            }],
        )
        db.add(claim1)
        
        claim2 = Claim(
            policy_id=policy.policy_id,
            claim_number="INC-2024-002345",
            claim_type=ClaimType.INCIDENT,
            status=ClaimStatus.UNDER_REVIEW,
            incident_date=date(2024, 10, 5),
            loss_amount=Decimal("7200.00"),
            claim_metadata={
                "description": "Collision with deer on highway",
                "location": "I-87 North, near Exit 15",
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
                    "notes": "Assigned to adjuster",
                },
            ],
        )
        db.add(claim2)
        print("      > Added 2 claims")
        
        # System settings
        settings = [
            ("llm_provider", "openai", "Active LLM provider"),
            ("openai_model", "gpt-4o-mini", "OpenAI model"),
            ("openai_vision_model", "gpt-4o-mini", "OpenAI vision model"),
            ("confidence_threshold", 0.7, "AI confidence threshold"),
            ("auto_approval_limit", 5000.0, "Auto-approval limit"),
        ]
        for key, value, desc in settings:
            db.add(SystemSettings(key=key, value=value, description=desc))
        print("      > Added system settings")
        
        db.commit()
        
        print("\n" + "="*70)
        print("SUCCESS! Database reset complete")
        print("="*70)
        print("\nLOGIN CREDENTIALS:")
        print("-"*70)
        print("CUSTOMER (John Smith):")
        print("  Email:    john.smith@example.com")
        print("  Password: demo123")
        print("  Policy:   AUTO-123456")
        print("  Vehicles: 2023 Honda Accord, 2021 Toyota Highlander")
        print("  Drivers:  John (Primary), Sarah (Spouse)")
        print("  Claims:   2 sample claims")
        print("\nADMIN:")
        print("  Email:    admin@claimbot.demo")
        print("  Password: admin123")
        print("\nCELEST (Claims Adjuster):")
        print("  Email:    celest@claimbot.demo")
        print("  Password: celest123")
        print("="*70)
        
    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    reset_database()
