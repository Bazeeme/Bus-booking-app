
CREATE TABLE IF NOT EXISTS bookings (
    name VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
    departure_date DATE NOT NULL,
    source VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    CHECK (LOWER(TRIM(source)) <> LOWER(TRIM(destination)))
);

CREATE INDEX IF NOT EXISTS idx_bookings_departure_date
ON bookings (departure_date);

CREATE INDEX IF NOT EXISTS idx_bookings_email
ON bookings (email);