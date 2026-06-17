"""Builds fincommerce.db: a SQLite database with realistic banking + retail
data, used as the backing store for SQL interview questions."""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

DB_PATH = Path(__file__).parent / "fincommerce.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

fake = Faker()
random.seed(42)
Faker.seed(42)

REGIONS = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
SEGMENTS = ["Retail", "Premium", "Business"]
ACCOUNT_TYPES = ["Checking", "Savings", "Business"]
LOAN_TYPES = ["Auto", "Mortgage", "Personal", "Business"]
CATEGORIES = {
    "Electronics": ["Wireless Earbuds", "4K Monitor", "Mechanical Keyboard", "Smartwatch", "Bluetooth Speaker"],
    "Home": ["Air Fryer", "Robot Vacuum", "Coffee Maker", "Standing Desk", "Desk Lamp"],
    "Outdoors": ["Camping Tent", "Hiking Backpack", "Insulated Bottle", "Trail Shoes", "Sleeping Bag"],
    "Office": ["Ergonomic Chair", "Notebook Set", "Laser Printer", "Webcam", "Label Maker"],
}


def random_date(start_year=2018, end_year=2025):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def build():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())

    # branches
    branches = []
    for i in range(1, 9):
        branches.append((i, f"{fake.city()} Branch", fake.city(), random.choice(REGIONS), random_date(2010, 2018)))
    conn.executemany("INSERT INTO branches VALUES (?,?,?,?,?)", branches)

    # customers
    customers = []
    for i in range(1, 201):
        customers.append((
            i, fake.first_name(), fake.last_name(), fake.unique.email(),
            random_date(2018, 2024), fake.city(), random.choice(SEGMENTS),
            random.randint(1, len(branches)),
        ))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)

    # accounts (1-3 per customer)
    accounts = []
    account_id = 1
    for c in customers:
        customer_id, branch_id = c[0], c[7]
        for _ in range(random.randint(1, 3)):
            accounts.append((
                account_id, customer_id, branch_id, random.choice(ACCOUNT_TYPES),
                random_date(2018, 2025), round(random.uniform(50, 50000), 2),
                random.choices(["Active", "Dormant", "Closed"], weights=[0.8, 0.15, 0.05])[0],
            ))
            account_id += 1
    conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?,?)", accounts)

    # cards (1-2 per account)
    cards = []
    card_id = 1
    for acc in accounts:
        acc_id = acc[0]
        for _ in range(random.randint(1, 2)):
            card_type = random.choice(["Debit", "Credit"])
            cards.append((
                card_id, acc_id, card_type,
                round(random.uniform(1000, 20000), 2) if card_type == "Credit" else None,
                random_date(2019, 2025), random.choices(["Active", "Blocked", "Expired"], weights=[0.85, 0.05, 0.10])[0],
            ))
            card_id += 1
    conn.executemany("INSERT INTO cards VALUES (?,?,?,?,?,?)", cards)

    # transactions (5-40 per account)
    transactions = []
    txn_id = 1
    txn_types = ["Deposit", "Withdrawal", "Transfer", "Purchase", "Fee"]
    for acc in accounts:
        acc_id = acc[0]
        for _ in range(random.randint(5, 40)):
            txn_type = random.choices(txn_types, weights=[0.25, 0.2, 0.2, 0.25, 0.1])[0]
            amount = round(random.uniform(5, 3000), 2)
            if txn_type in ("Withdrawal", "Purchase", "Fee"):
                amount = -amount
            transactions.append((
                txn_id, acc_id, random_date(2020, 2025), txn_type, amount,
                f"{txn_type} - {fake.word()}",
            ))
            txn_id += 1
    conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?)", transactions)

    # loans (some customers have 0-2)
    loans = []
    loan_id = 1
    for c in customers:
        customer_id, branch_id = c[0], c[7]
        for _ in range(random.choices([0, 1, 2], weights=[0.5, 0.4, 0.1])[0]):
            loan_type = random.choice(LOAN_TYPES)
            principal = {
                "Auto": random.uniform(8000, 40000),
                "Mortgage": random.uniform(120000, 600000),
                "Personal": random.uniform(1000, 20000),
                "Business": random.uniform(20000, 250000),
            }[loan_type]
            loans.append((
                loan_id, customer_id, branch_id, loan_type, round(principal, 2),
                round(random.uniform(2.5, 9.5), 2), random_date(2018, 2024),
                random.choice([12, 24, 36, 48, 60, 120, 240, 360]),
                random.choices(["Active", "Paid Off", "Default"], weights=[0.65, 0.3, 0.05])[0],
            ))
            loan_id += 1
    conn.executemany("INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?)", loans)

    # products
    products = []
    product_id = 1
    for category, names in CATEGORIES.items():
        for name in names:
            products.append((product_id, name, category, round(random.uniform(15, 800), 2)))
            product_id += 1
    conn.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    # orders + order_items (only customers with active credit/debit cards order)
    orders = []
    order_items = []
    order_id = 1
    order_item_id = 1
    cards_by_customer = {}
    for card in cards:
        c_id, acc_id = card[0], card[1]
        owner = next(a[1] for a in accounts if a[0] == acc_id)
        cards_by_customer.setdefault(owner, []).append(c_id)

    for customer_id, card_ids in cards_by_customer.items():
        for _ in range(random.randint(0, 6)):
            order_date = random_date(2021, 2025)
            orders.append((
                order_id, customer_id, random.choice(card_ids), order_date,
                random.choices(["Completed", "Refunded", "Cancelled"], weights=[0.85, 0.1, 0.05])[0],
            ))
            for _ in range(random.randint(1, 4)):
                product = random.choice(products)
                order_items.append((
                    order_item_id, order_id, product[0], random.randint(1, 3), product[3],
                ))
                order_item_id += 1
            order_id += 1

    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", order_items)

    conn.commit()
    conn.close()
    print(f"Built {DB_PATH} with {len(customers)} customers, {len(accounts)} accounts, "
          f"{len(transactions)} transactions, {len(loans)} loans, {len(orders)} orders.")


if __name__ == "__main__":
    build()
