# Database connection lifecycle (regression for intermittent
# sqlite3.ProgrammingError: "SQLite objects created in a thread can only be
# used in that same thread" when uvicorn serves the first requests).

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import db


def test_connection_can_be_used_from_another_thread(db_path):
    """Regression: FastAPI creates the connection on one anyio worker
    thread and runs the endpoint and teardown on potentially different
    worker threads. A per-request connection must tolerate that hand-off.
    With check_same_thread=True (the old default), the query below raises
    sqlite3.ProgrammingError on the thread that did not create the
    connection.
    """
    conn = db.connect()  # created on the test's main thread
    errors: list[Exception] = []

    def run(fn):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - collected for assertions
            errors.append(exc)

    # Execute and close on a worker thread, as uvicorn would.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(run, lambda: conn.execute("SELECT 1").fetchone()).result()
        pool.submit(run, conn.close).result()

    assert not errors, f"cross-thread use failed: {errors!r}"


def test_get_connection_closes_even_when_endpoint_raises(db_path):
    """The dependency must close the connection when the endpoint body
    raises (FastAPI throws the exception into the generator during
    teardown), and the closed connection must reject further queries.
    """
    gen = db.get_connection()
    conn = next(gen)
    with pytest.raises(RuntimeError, match="endpoint failed"):
        gen.throw(RuntimeError("endpoint failed"))

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_get_connection_yields_fresh_connection_per_request(db_path):
    """Each dependency invocation must open its own connection (no shared
    global connection) and close it on exit.
    """
    first = db.get_connection()
    conn_one = next(first)
    second = db.get_connection()
    conn_two = next(second)
    try:
        assert conn_one is not conn_two
    finally:
        second.close()
        first.close()

    # Both connections are closed after their generators finish.
    for conn in (conn_one, conn_two):
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_get_connection_yields_usable_connection(db_path):
    """Sanity: the dependency yields an open connection with Row factory
    and foreign keys enabled.
    """
    gen = db.get_connection()
    conn = next(gen)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _probe (
                id INTEGER PRIMARY KEY,
                parent INTEGER REFERENCES _probe(id)
            )
            """
        )
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1
    finally:
        gen.close()

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
