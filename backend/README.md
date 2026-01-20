# ClaimBot Backend

Insurance claims automation backend with FastAPI, PostgreSQL, and LangGraph.

## Setup

1. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
copy .env.example .env
# Edit .env with your PostgreSQL credentials
```

4. Run migrations:
```bash
alembic upgrade head
```

5. Seed database:
```bash
python -m data.generator.seed
```

6. Start server:
```bash
uvicorn main:app --reload
```

## Project Structure

```
backend/
├── app/
│   ├── api/routes/      # API endpoints
│   ├── core/            # Config, security, logging
│   ├── db/models/       # SQLAlchemy models
│   ├── services/        # Business logic
│   ├── orchestration/   # LangGraph graphs and tools
│   └── websocket/       # Real-time chat
├── data/generator/      # Synthetic data generation
├── tests/               # Unit and integration tests
├── alembic/             # Database migrations
└── main.py              # FastAPI app entry
```
