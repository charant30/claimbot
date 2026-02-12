"""
Seed script for populating the database with sample policies.
Run with: python data/seed_policies.py
"""
import json
import sys
from pathlib import Path
from datetime import date
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.db.models import User, Policy, PolicyCoverage, PolicyVehicle, PolicyDriver, ProductType, PolicyStatus
from app.db.models.user import UserRole


def load_sample_policies():
    """Load sample policies from JSON files."""
    sample_dir = Path(__file__).parent / "sample_policies"
    policies = []

    for json_file in sample_dir.glob("*.json"):
        with open(json_file, "r") as f:
            policies.append(json.load(f))

    return policies


def get_or_create_user(db: Session, email: str, name: str) -> User:
    """Get existing user or create new one."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            user_id=uuid4(),
            email=email,
            name=name,
            password_hash="sample_user_no_login",  # Sample users can't login
            role=UserRole.CUSTOMER,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"  Created user: {name} ({email})")
    else:
        print(f"  Found existing user: {name} ({email})")
    return user


def map_driver_relationship(rel_str: str) -> str:
    """Map relationship string to lowercase enum value for PostgreSQL."""
    valid_values = {"self", "spouse", "child", "parent", "other_relative", "other"}
    value = rel_str.lower()
    return value if value in valid_values else "other"


def seed_policies():
    """Seed the database with sample policies."""
    print("\n" + "="*60)
    print("SEEDING DATABASE WITH SAMPLE POLICIES")
    print("="*60 + "\n")

    db = SessionLocal()

    try:
        policies_data = load_sample_policies()
        print(f"Found {len(policies_data)} sample policies\n")

        for policy_data in policies_data:
            policy_number = policy_data["policy_number"]

            # Check if policy already exists
            existing = db.query(Policy).filter(
                Policy.policy_number == policy_number
            ).first()

            if existing:
                print(f"  Skipping {policy_number} (already exists)")
                continue

            print(f"Processing {policy_number}...")

            # Get or create user
            holder = policy_data["holder"]
            user = get_or_create_user(db, holder["email"], holder.get("name", f"{holder.get('first_name', '')} {holder.get('last_name', '')}"))

            # Map product type
            product_type = ProductType(policy_data["product_type"])

            # Create policy with holder details
            policy = Policy(
                policy_id=uuid4(),
                policy_number=policy_number,
                user_id=user.user_id,
                product_type=product_type,
                effective_date=date.fromisoformat(policy_data["effective_date"]),
                expiration_date=date.fromisoformat(policy_data["expiration_date"]),
                status=PolicyStatus.ACTIVE,
                # Holder details for identity matching
                holder_first_name=holder.get("first_name"),
                holder_last_name=holder.get("last_name"),
                holder_phone=holder.get("phone"),
                holder_email=holder.get("email"),
                holder_dob=date.fromisoformat(holder["date_of_birth"]) if holder.get("date_of_birth") else None,
                holder_address=holder.get("address"),
                holder_zip=holder.get("zip"),
            )
            db.add(policy)
            db.flush()  # Get policy_id

            # Add coverages
            for cov_data in policy_data.get("coverages", []):
                coverage = PolicyCoverage(
                    coverage_id=uuid4(),
                    policy_id=policy.policy_id,
                    coverage_type=cov_data["coverage_type"],
                    limit_amount=cov_data["limit_amount"],
                    deductible=cov_data.get("deductible", 0),
                    daily_limit=cov_data.get("daily_limit"),
                    max_days=cov_data.get("max_days"),
                )
                db.add(coverage)

            # Add vehicles for auto policies
            for veh_data in policy_data.get("vehicles", []):
                vehicle = PolicyVehicle(
                    vehicle_id=uuid4(),
                    policy_id=policy.policy_id,
                    vin=veh_data["vin"],
                    year=veh_data["year"],
                    make=veh_data["make"],
                    model=veh_data["model"],
                    trim=veh_data.get("trim"),
                    body_type=veh_data.get("body_type"),
                    color=veh_data.get("color"),
                    license_plate=veh_data.get("license_plate"),
                    license_state=veh_data.get("license_state"),
                    ownership_status=veh_data.get("ownership_status"),
                    annual_mileage=veh_data.get("annual_mileage"),
                    primary_use=veh_data.get("primary_use"),
                    is_active=True,
                )
                db.add(vehicle)

            # Add drivers for auto policies
            for drv_data in policy_data.get("drivers", []):
                driver = PolicyDriver(
                    driver_id=uuid4(),
                    policy_id=policy.policy_id,
                    first_name=drv_data["first_name"],
                    last_name=drv_data["last_name"],
                    date_of_birth=date.fromisoformat(drv_data["date_of_birth"]),
                    gender=drv_data.get("gender"),
                    license_number=drv_data["license_number"],
                    license_state=drv_data["license_state"],
                    license_status=drv_data.get("license_status", "valid"),
                    license_expiration=date.fromisoformat(drv_data["license_expiration"]) if drv_data.get("license_expiration") else None,
                    driver_relationship=map_driver_relationship(drv_data.get("relationship", "other")),
                    is_primary=drv_data.get("is_primary", False),
                    years_licensed=drv_data.get("years_licensed"),
                    accidents_3yr=drv_data.get("accidents_3yr", 0),
                    violations_3yr=drv_data.get("violations_3yr", 0),
                    is_active=True,
                    is_excluded=False,
                )
                db.add(driver)

            db.commit()

            # Log what was created
            num_coverages = len(policy_data.get('coverages', []))
            num_vehicles = len(policy_data.get('vehicles', []))
            num_drivers = len(policy_data.get('drivers', []))
            print(f"  Created policy with {num_coverages} coverages, {num_vehicles} vehicles, {num_drivers} drivers")

        print("\n" + "="*60)
        print("SEEDING COMPLETE!")
        print("="*60)

        # Summary
        total_users = db.query(User).count()
        total_policies = db.query(Policy).count()
        total_coverages = db.query(PolicyCoverage).count()
        total_vehicles = db.query(PolicyVehicle).count()
        total_drivers = db.query(PolicyDriver).count()

        print(f"\nDatabase Summary:")
        print(f"  Users: {total_users}")
        print(f"  Policies: {total_policies}")
        print(f"  Policy Coverages: {total_coverages}")
        print(f"  Policy Vehicles: {total_vehicles}")
        print(f"  Policy Drivers: {total_drivers}")
        print()

    except Exception as e:
        print(f"\nError: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_policies()
