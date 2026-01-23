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
from app.db.models import User, Policy, PolicyCoverage, ProductType, PolicyStatus
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
                print(f"⏭️  Skipping {policy_number} (already exists)")
                continue
            
            print(f"📋 Processing {policy_number}...")
            
            # Get or create user
            holder = policy_data["holder"]
            user = get_or_create_user(db, holder["email"], holder["name"])
            
            # Map product type
            product_type = ProductType(policy_data["product_type"])
            
            # Create policy
            policy = Policy(
                policy_id=uuid4(),
                policy_number=policy_number,
                user_id=user.user_id,
                product_type=product_type,
                effective_date=date.fromisoformat(policy_data["effective_date"]),
                expiration_date=date.fromisoformat(policy_data["expiration_date"]),
                status=PolicyStatus.ACTIVE,
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
                )
                db.add(coverage)
            
            db.commit()
            print(f"  ✅ Created policy with {len(policy_data.get('coverages', []))} coverages")
        
        print("\n" + "="*60)
        print("SEEDING COMPLETE!")
        print("="*60)
        
        # Summary
        total_users = db.query(User).count()
        total_policies = db.query(Policy).count()
        total_coverages = db.query(PolicyCoverage).count()
        
        print(f"\nDatabase Summary:")
        print(f"  Users: {total_users}")
        print(f"  Policies: {total_policies}")
        print(f"  Policy Coverages: {total_coverages}")
        print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_policies()
