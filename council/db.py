import os

from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://council:council@localhost:5432/council")

# The single application engine. Persistence goes through council.run_store.RunStore,
# which builds its own sessions from an injected engine — Postgres here, in-memory
# SQLite in tests.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
