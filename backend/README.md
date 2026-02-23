# ClaimBot Backend

FastAPI + PostgreSQL + LangGraph backend for insurance claims automation.

## Setup

1. **Virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```

2. **Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment** — copy `.env.example` to `.env` and set `DATABASE_URL` (and other keys as needed).
   - Windows: `copy .env.example .env`

4. **Migrations**
   ```bash
   alembic upgrade head
   ```

5. **Seed** (one demo customer with policy, vehicles, drivers, claims; plus admin and Celest users)
   ```bash
   python -m data.generator.fresh_start
   ```

6. **Run**
   ```bash
   uvicorn main:app --reload
   ```

## Structure

- `app/api/routes/` — API endpoints  
- `app/core/` — Config, security, logging  
- `app/db/models/` — SQLAlchemy models  
- `app/services/` — Business logic  
- `app/orchestration/` — LangGraph graphs and tools  
- `data/generator/` — Seed script (fresh_start)  
- `tests/` — Tests  
- `alembic/` — Migrations  
- `main.py` — App entry
