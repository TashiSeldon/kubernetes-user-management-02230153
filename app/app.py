import os
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request

app = Flask(__name__)

DB = {
    "host": os.getenv("DB_HOST", "postgres"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "2")),
}
DB_CONNECT_ATTEMPTS = max(1, int(os.getenv("DB_CONNECT_ATTEMPTS", "2")))


def connect(*, attempts=None):
    """Open a connection, retrying only the connection step."""
    attempts = DB_CONNECT_ATTEMPTS if attempts is None else max(1, attempts)
    for attempt in range(attempts):
        try:
            return psycopg2.connect(**DB, cursor_factory=RealDictCursor)
        except psycopg2.OperationalError:
            if attempt + 1 == attempts:
                raise
            time.sleep(0.2)


@contextmanager
def database_connection(*, attempts=None):
    """Finish the transaction and always close the database socket."""
    conn = connect(attempts=attempts)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_database():
    # Each attempt has a two-second connection timeout. Thirty attempts with
    # one-second backoff keep startup bounded while tolerating a brief outage.
    for attempt in range(30):
        try:
            with database_connection(attempts=1) as conn, conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE
                )""")
            return
        except psycopg2.OperationalError:
            if attempt == 29:
                raise
            time.sleep(1)


initialize_database()


@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200


@app.get("/ready")
def ready():
    try:
        # Readiness checks fail promptly when PostgreSQL is unavailable.
        with database_connection(attempts=1) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ready"), 200
    except psycopg2.Error as error:
        app.logger.warning("Readiness check failed: %s", error)
        return jsonify(error="database unavailable"), 503


@app.errorhandler(psycopg2.OperationalError)
def database_unavailable(error):
    app.logger.exception("Database operation failed")
    return jsonify(error="database unavailable"), 503


@app.get("/users")
def list_users():
    with database_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users ORDER BY id")
        return jsonify(cur.fetchall())


@app.post("/users")
def create_user():
    body = request.get_json(silent=True) or {}
    if not body.get("name") or not body.get("email"):
        return jsonify(error="name and email are required"), 400
    try:
        with database_connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id, name, email",
                        (body["name"], body["email"]))
            created = cur.fetchone()
        return jsonify(created), 201
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="email already exists"), 409


@app.get("/users/<int:user_id>")
def get_user(user_id):
    with database_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
    return (jsonify(user), 200) if user else (jsonify(error="user not found"), 404)


@app.put("/users/<int:user_id>")
def update_user(user_id):
    body = request.get_json(silent=True) or {}
    if not body.get("name") or not body.get("email"):
        return jsonify(error="name and email are required"), 400
    try:
        with database_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET name = %s, email = %s WHERE id = %s RETURNING id, name, email",
                        (body["name"], body["email"], user_id))
            user = cur.fetchone()
        return (jsonify(user), 200) if user else (jsonify(error="user not found"), 404)
    except psycopg2.errors.UniqueViolation:
        return jsonify(error="email already exists"), 409


@app.delete("/users/<int:user_id>")
def delete_user(user_id):
    with database_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
        deleted = cur.fetchone()
    return ("", 204) if deleted else (jsonify(error="user not found"), 404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
