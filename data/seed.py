# data/seed.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Generate synthetic e-commerce data with realistic patterns.
Run once: uv run python data/seed.py

Injects anomalies in the last 2 days:
- Mobile conversion rate drops 40%
- Electronics category revenue drops 35%
- Refund rate spikes in Electronics
"""

import random
import psycopg2
from datetime import datetime, timedelta
from config.settings import settings

random.seed(42)

CATEGORIES = ["Electronics", "Clothing", "Home", "Sports", "Beauty"]
CHANNELS = ["organic", "paid_search", "email", "social", "direct"]
DEVICES = ["mobile", "desktop", "tablet"]
COUNTRIES = ["UK", "US", "DE", "FR", "AU"]
REFUND_REASONS = ["defective", "wrong_item", "changed_mind", "not_as_described"]

CATEGORY_PRICES = {
    "Electronics": (80, 800),
    "Clothing": (20, 150),
    "Home": (30, 300),
    "Sports": (25, 200),
    "Beauty": (15, 80),
}

# Device conversion rates (baseline)
DEVICE_CONVERSION = {
    "mobile": 0.028,
    "desktop": 0.042,
    "tablet": 0.035,
}

# Channel session volumes
CHANNEL_WEIGHT = {
    "organic": 0.35,
    "paid_search": 0.25,
    "email": 0.15,
    "social": 0.15,
    "direct": 0.10,
}


def get_conn():
    return psycopg2.connect(settings.postgres_url)


def create_schema(conn):
    with open("data/schema.sql") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Schema created.")


def seed_orders(conn, date: datetime, anomaly: bool = False):
    """Generate orders for a single day."""
    # Normal: 800-1200 orders/day
    n_orders = random.randint(800, 1200)

    rows = []
    for _ in range(n_orders):
        category = random.choices(
            CATEGORIES,
            weights=[0.30, 0.25, 0.20, 0.15, 0.10]
        )[0]
        device = random.choices(DEVICES, weights=[0.55, 0.35, 0.10])[0]
        channel = random.choices(
            list(CHANNEL_WEIGHT.keys()),
            weights=list(CHANNEL_WEIGHT.values())
        )[0]
        country = random.choices(
            COUNTRIES,
            weights=[0.35, 0.30, 0.15, 0.12, 0.08]
        )[0]

        lo, hi = CATEGORY_PRICES[category]
        unit_price = round(random.uniform(lo, hi), 2)

        # Anomaly: Electronics revenue drops 35%
        if anomaly and category == "Electronics":
            if random.random() < 0.35:
                continue  # skip this order — simulates 35% drop

        discount = round(random.choice([0, 0, 0, 5, 10, 15, 20]), 2)
        revenue = round(unit_price * (1 - discount / 100), 2)

        ts = date + timedelta(
            hours=random.randint(6, 23),
            minutes=random.randint(0, 59),
        )

        rows.append((
            random.randint(1000, 50000),  # customer_id
            ts,
            random.randint(1, 500),       # product_id
            category,
            channel,
            device,
            country,
            1,
            unit_price,
            discount,
            revenue,
            "completed",
        ))

    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO orders
                (customer_id, created_at, product_id, category, channel,
                 device_type, country, quantity, unit_price, discount_pct,
                 revenue, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
    conn.commit()
    return len(rows)


def seed_sessions(conn, date: datetime, anomaly: bool = False):
    """Generate web sessions for a single day."""
    n_sessions = random.randint(8000, 12000)

    rows = []
    for _ in range(n_sessions):
        device = random.choices(DEVICES, weights=[0.60, 0.30, 0.10])[0]
        channel = random.choices(
            list(CHANNEL_WEIGHT.keys()),
            weights=list(CHANNEL_WEIGHT.values())
        )[0]
        country = random.choices(
            COUNTRIES,
            weights=[0.35, 0.30, 0.15, 0.12, 0.08]
        )[0]

        # Anomaly: mobile conversion drops 40%
        conv_rate = DEVICE_CONVERSION[device]
        if anomaly and device == "mobile":
            conv_rate *= 0.60  # 40% drop

        converted = random.random() < conv_rate
        bounced = not converted and random.random() < 0.45

        ts = date + timedelta(
            hours=random.randint(6, 23),
            minutes=random.randint(0, 59),
        )

        rows.append((
            ts,
            random.randint(1000, 50000) if converted else None,
            device,
            channel,
            country,
            random.randint(1, 15),
            random.randint(30, 600) if not bounced else random.randint(5, 30),
            converted,
            bounced,
        ))

    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO sessions
                (created_at, customer_id, device_type, channel,
                 country, pages_viewed, duration_seconds,
                 converted, bounced)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, rows)
    conn.commit()
    return len(rows)


def seed_refunds(conn, date: datetime, anomaly: bool = False):
    """Generate refunds for a single day."""
    n_refunds = random.randint(20, 50)
    if anomaly:
        n_refunds = random.randint(80, 120)  # spike

    with conn.cursor() as cur:
        cur.execute(
            "SELECT order_id, revenue, category FROM orders "
            "WHERE created_at::date = %s LIMIT 500",
            (date.date(),)
        )
        orders = cur.fetchall()

    if not orders:
        return 0

    rows = []
    for _ in range(min(n_refunds, len(orders))):
        order = random.choice(orders)
        order_id, revenue, category = order

        # Anomaly: Electronics refunds spike
        reason = random.choice(REFUND_REASONS)
        if anomaly and category == "Electronics":
            reason = random.choice(["defective", "not_as_described"])

        ts = date + timedelta(
            hours=random.randint(8, 20),
            minutes=random.randint(0, 59),
        )
        rows.append((order_id, ts, reason, round(float(revenue) * 0.95, 2)))

    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO refunds (order_id, created_at, reason, amount)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, rows)
    conn.commit()
    return len(rows)


def seed_campaigns(conn):
    """Add a few campaigns to the calendar."""
    campaigns = [
        ("Summer Sale", "2026-04-15", "2026-04-20", "email", 15.0),
        ("Paid Search Push", "2026-05-01", "2026-05-07", "paid_search", 10.0),
        ("Social Campaign", "2026-05-20", "2026-05-25", "social", 8.0),
    ]
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO campaign_calendar
                (campaign_name, start_date, end_date, channel, expected_uplift_pct)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, campaigns)
    conn.commit()
    print(f"Seeded {len(campaigns)} campaigns.")


def main():
    conn = get_conn()
    create_schema(conn)
    seed_campaigns(conn)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=90)

    print(f"Seeding 90 days of data from {start.date()} to {today.date()}...")

    for i in range(90):
        date = start + timedelta(days=i)
        # Inject anomaly in the last 2 days
        anomaly = i >= 88

        orders = seed_orders(conn, date, anomaly)
        sessions = seed_sessions(conn, date, anomaly)
        refunds = seed_refunds(conn, date, anomaly)

        if i % 10 == 0 or anomaly:
            flag = " ← ANOMALY INJECTED" if anomaly else ""
            print(f"  {date.date()}: {orders} orders, "
                  f"{sessions} sessions, {refunds} refunds{flag}")

    conn.close()
    print("Seeding complete.")


if __name__ == "__main__":
    main()