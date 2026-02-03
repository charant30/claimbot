
import sys
import os

# Add the current directory to sys.path to ensure 'app' can be imported
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import User

def list_emails():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("No users found in the database. You might need to run the seed script.")
            return
            
        print("\n--- Registered User Emails ---")
        for user in users:
            print(f"Email: {user.email:<30} | Role: {user.role.value}")
        print("--- End of List ---\n")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_emails()
