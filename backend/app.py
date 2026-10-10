
import os
import sqlite3
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env.local", override=True)

app = Flask(__name__)
LOCAL_MODE = not os.getenv("DB_HOST")
FRONTEND_DIR = ROOT_DIR / "frontend"
LOCAL_DATABASE_PATH = (
    Path(os.getenv("LOCALAPPDATA", str(Path.home())))
    / "EasyBus"
    / "busbookings.sqlite3"
)


def get_db():
    if LOCAL_MODE:
        LOCAL_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(LOCAL_DATABASE_PATH, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5
    )


def initialize_local_database():
    connection = get_db()
    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS booking (
                name VARCHAR(100) NOT NULL,
                email VARCHAR(254) NOT NULL,
                age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
                date TEXT NOT NULL,
                source VARCHAR(100) NOT NULL,
                destination VARCHAR(100) NOT NULL,
                CHECK (LOWER(TRIM(source)) <> LOWER(TRIM(destination)))
            );
            CREATE INDEX IF NOT EXISTS idx_booking_date
                ON booking (date);
            CREATE INDEX IF NOT EXISTS idx_booking_email
                ON booking (email);
        """)
    finally:
        connection.close()


def migrate_booking_columns():
    connection = get_db()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS booking (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        email VARCHAR(254) NOT NULL,
                        age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
                        date DATE NOT NULL,
                        source VARCHAR(100) NOT NULL,
                        destination VARCHAR(100) NOT NULL,
                        CHECK (LOWER(TRIM(source)) <> LOWER(TRIM(destination)))
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_booking_date ON booking (date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_booking_email ON booking (email)")
                cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'bookings')")
                if cursor.fetchone()[0]:
                    cursor.execute("""
                        INSERT INTO booking (name, email, age, date, source, destination)
                        SELECT name, email, age, departure_date, source, destination FROM bookings
                        ON CONFLICT DO NOTHING
                    """)
                    cursor.execute("DROP TABLE bookings")
    finally:
        connection.close()


def wait_for_database():
    for attempt in range(30):
        try:
            connection = get_db()
            connection.close()
            print("PostgreSQL connected successfully.")
            return
        except psycopg2.OperationalError:
            if attempt == 29:
                raise
            print("Waiting for PostgreSQL...")
            time.sleep(2)


@app.get("/api/health")
def health():
    connection = get_db()
    try:
        if LOCAL_MODE:
            connection.execute("SELECT 1")
        else:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        return jsonify({"status": "ok", "database": "connected"})
    finally:
        connection.close()


@app.post("/api/bookings")
def create_booking():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Please submit valid booking details."}), 400

    name = data.get("name")
    email = data.get("email")
    source = data.get("source")
    destination = data.get("destination")
    departure_date = data.get("departure_date")

    if not all(isinstance(value, str) for value in [
        name, email, source, destination, departure_date
    ]):
        return jsonify({"error": "All fields are required."}), 400

    name = name.strip()
    email = email.strip()
    source = source.strip()
    destination = destination.strip()

    if not name or len(name) > 100:
        return jsonify({"error": "Name must be 1–100 characters."}), 400

    if (
        not email or len(email) > 254
        or "@" not in email
        or email.startswith("@")
        or email.endswith("@")
    ):
        return jsonify({"error": "Enter a valid email address."}), 400

    if not source or len(source) > 100:
        return jsonify({"error": "Enter a valid source."}), 400

    if not destination or len(destination) > 100:
        return jsonify({"error": "Enter a valid destination."}), 400

    if source.casefold() == destination.casefold():
        return jsonify({
            "error": "Source and destination must be different."
        }), 400

    age = data.get("age")

    # Reject booleans and non-integer ages.
    if isinstance(age, bool) or not isinstance(age, int) or not 1 <= age <= 120:
        return jsonify({"error": "Age must be between 1 and 120."}), 400

    try:
        journey_date = date.fromisoformat(departure_date)
    except ValueError:
        return jsonify({"error": "Enter a valid departure date."}), 400

    if journey_date < date.today():
        return jsonify({"error": "Departure date cannot be in the past."}), 400

    connection = get_db()

    try:
        with connection:
            if LOCAL_MODE:
                cursor = connection.execute("""
                    INSERT INTO booking
                        (name, email, age, date, source, destination)
                    VALUES (?, ?, ?, ?, ?, ?)
                    RETURNING name, email, age,
                              date, source, destination
                """, (
                    name,
                    email,
                    age,
                    journey_date.isoformat(),
                    source,
                    destination
                ))
                booking = cursor.fetchone()
            else:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        INSERT INTO booking
                            (name, email, age, date, source, destination)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING name, email, age,
                                  date, source, destination
                    """, (
                        name,
                        email,
                        age,
                        journey_date,
                        source,
                        destination
                    ))
                    booking = cursor.fetchone()

        booking = dict(booking)
        if "date" in booking and hasattr(booking["date"], "isoformat"):
            booking["date"] = booking["date"].isoformat()
        if "date" in booking:
            booking["departure_date"] = booking["date"]
            booking.pop("date")

        return jsonify({
            "message": "Booking confirmed successfully!",
            "booking": booking
        }), 201

    except (psycopg2.Error, sqlite3.Error):
        app.logger.exception("Database booking operation failed.")
        return jsonify({
            "error": "Unable to save your booking. Please try again."
        }), 500
    finally:
        connection.close()


if FRONTEND_DIR.is_dir():
    @app.get("/")
    def frontend_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:asset_name>")
    def frontend_asset(asset_name):
        return send_from_directory(FRONTEND_DIR, asset_name)


if __name__ == "__main__":
    if LOCAL_MODE:
        initialize_local_database()
        print(f"Local SQLite database: {LOCAL_DATABASE_PATH}")
    else:
        wait_for_database()
        migrate_booking_columns()
    app.run(host="0.0.0.0", port=5000)