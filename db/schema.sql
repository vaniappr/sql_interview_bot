-- FinCommerce: a fictional bank that also runs a retail/merchant arm.
-- Schema spans banking (accounts, transactions, loans, cards) and
-- commerce (products, orders, order_items) so interview questions can
-- span joins across both domains.

CREATE TABLE branches (
    branch_id     INTEGER PRIMARY KEY,
    branch_name   TEXT NOT NULL,
    city          TEXT NOT NULL,
    region        TEXT NOT NULL,
    opened_date   DATE NOT NULL
);

CREATE TABLE customers (
    customer_id    INTEGER PRIMARY KEY,
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    email          TEXT NOT NULL,
    signup_date    DATE NOT NULL,
    city           TEXT NOT NULL,
    segment        TEXT NOT NULL,           -- e.g. Retail, Premium, Business
    branch_id      INTEGER REFERENCES branches(branch_id)
);

CREATE TABLE accounts (
    account_id     INTEGER PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers(customer_id),
    branch_id      INTEGER NOT NULL REFERENCES branches(branch_id),
    account_type   TEXT NOT NULL,           -- Checking, Savings, Business
    opened_date    DATE NOT NULL,
    balance        REAL NOT NULL,
    status         TEXT NOT NULL            -- Active, Dormant, Closed
);

CREATE TABLE transactions (
    transaction_id   INTEGER PRIMARY KEY,
    account_id       INTEGER NOT NULL REFERENCES accounts(account_id),
    txn_date         DATE NOT NULL,
    txn_type         TEXT NOT NULL,         -- Deposit, Withdrawal, Transfer, Purchase, Fee
    amount           REAL NOT NULL,         -- positive = credit, negative = debit
    description      TEXT
);

CREATE TABLE loans (
    loan_id         INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    branch_id       INTEGER NOT NULL REFERENCES branches(branch_id),
    loan_type       TEXT NOT NULL,          -- Auto, Mortgage, Personal, Business
    principal       REAL NOT NULL,
    interest_rate   REAL NOT NULL,
    issued_date     DATE NOT NULL,
    term_months     INTEGER NOT NULL,
    status          TEXT NOT NULL           -- Active, Paid Off, Default
);

CREATE TABLE cards (
    card_id         INTEGER PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(account_id),
    card_type       TEXT NOT NULL,          -- Debit, Credit
    credit_limit    REAL,                   -- NULL for debit cards
    issued_date     DATE NOT NULL,
    status          TEXT NOT NULL
);

CREATE TABLE products (
    product_id      INTEGER PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    unit_price      REAL NOT NULL
);

CREATE TABLE orders (
    order_id        INTEGER PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(customer_id),
    card_id         INTEGER NOT NULL REFERENCES cards(card_id),
    order_date      DATE NOT NULL,
    status          TEXT NOT NULL           -- Completed, Refunded, Cancelled
);

CREATE TABLE order_items (
    order_item_id   INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(order_id),
    product_id      INTEGER NOT NULL REFERENCES products(product_id),
    quantity        INTEGER NOT NULL,
    unit_price      REAL NOT NULL
);
