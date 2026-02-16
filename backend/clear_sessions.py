"""
Clear all session data from the database for a fresh start.

Run from backend directory with venv:
  python clear_sessions.py
"""
import sys
import os

# Ensure backend app is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.db.models import Session


def main():
    db = SessionLocal()
    try:
        count = db.query(Session).count()
        db.query(Session).delete()
        db.commit()
        print(f"Cleared {count} session(s) from the database.")
        print("Sessions table is now empty. Restart the backend server to clear in-memory session cache.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
