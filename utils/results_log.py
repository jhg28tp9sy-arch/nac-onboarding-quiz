"""Persistent storage for identified NAC quiz results."""

import sqlite3
from contextlib import closing, contextmanager
from dataclasses import astuple, dataclass, fields


@dataclass(frozen=True)
class Learner:
    name: str
    staff_id: str | None = None


@dataclass(frozen=True)
class LoggedResult:
    attempt_id: str
    participant: str
    staff_id: str | None
    quiz: str
    attempt_type: str
    status: str
    completed_at_utc: str
    questions_answered: int
    quiz_questions: int
    score: int
    possible: int
    names_correct: int | None
    titles_correct: int | None


COLUMNS = tuple(field.name for field in fields(LoggedResult))
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS nac_quiz_results (
    attempt_id TEXT PRIMARY KEY,
    participant TEXT NOT NULL,
    staff_id TEXT,
    quiz TEXT NOT NULL,
    attempt_type TEXT NOT NULL,
    status TEXT NOT NULL,
    completed_at_utc TEXT NOT NULL,
    questions_answered INTEGER NOT NULL,
    quiz_questions INTEGER NOT NULL,
    score INTEGER NOT NULL,
    possible INTEGER NOT NULL,
    names_correct INTEGER,
    titles_correct INTEGER
)
"""


class ResultsStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResultsStore:
    database_url: str | None = None
    sqlite_path: str | None = None

    @contextmanager
    def connect(self):
        driver = sqlite3
        target = self.sqlite_path
        options = {"timeout": 4}
        if self.database_url:
            try:
                import psycopg as driver
            except ImportError as exc:
                raise ResultsStoreError("PostgreSQL driver unavailable.") from exc
            target = self.database_url
            options = {"connect_timeout": 4}
        try:
            with closing(driver.connect(target, **options)) as connection, connection:
                connection.execute(CREATE_TABLE)
                yield connection
        except (driver.Error, OSError) as exc:
            raise ResultsStoreError("Results database unavailable.") from exc

    def save(self, results):
        placeholder = "%s" if self.database_url else "?"
        values = ", ".join([placeholder] * len(COLUMNS))
        query = (f"INSERT INTO nac_quiz_results ({', '.join(COLUMNS)}) VALUES ({values}) "
                 "ON CONFLICT (attempt_id) DO NOTHING")
        with self.connect() as connection, closing(connection.cursor()) as cursor:
            cursor.executemany(query, (astuple(result) for result in results))

    def read(self):
        with self.connect() as connection:
            return connection.execute(
                f"SELECT {', '.join(COLUMNS)} FROM nac_quiz_results ORDER BY completed_at_utc DESC, attempt_id"
            ).fetchall()
