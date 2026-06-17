"""Question bank for the SQL interview chatbot.

Each question has a reference SQL solution; the grader runs both the
candidate's query and the reference query against the same database and
compares result sets (order-insensitive unless `ordered` is True).
"""

QUESTIONS = [
    {
        "id": 1,
        "difficulty": "Easy",
        "topic": "Filtering",
        "prompt": (
            "List the first_name, last_name, and city of all customers in the "
            "'Premium' segment."
        ),
        "solution": """
            SELECT first_name, last_name, city
            FROM customers
            WHERE segment = 'Premium'
        """,
        "ordered": False,
    },
    {
        "id": 2,
        "difficulty": "Easy",
        "topic": "Aggregation",
        "prompt": "How many accounts does each account_type have? Return account_type and the count.",
        "solution": """
            SELECT account_type, COUNT(*) AS account_count
            FROM accounts
            GROUP BY account_type
        """,
        "ordered": False,
    },
    {
        "id": 3,
        "difficulty": "Medium",
        "topic": "Joins",
        "prompt": (
            "For each branch, return branch_name and the total balance held across "
            "all of its accounts. Order by total balance descending."
        ),
        "solution": """
            SELECT b.branch_name, SUM(a.balance) AS total_balance
            FROM branches b
            JOIN accounts a ON a.branch_id = b.branch_id
            GROUP BY b.branch_name
            ORDER BY total_balance DESC
        """,
        "ordered": True,
    },
    {
        "id": 4,
        "difficulty": "Medium",
        "topic": "Joins + Filtering",
        "prompt": (
            "List customer_id and full name (first_name || ' ' || last_name as full_name) "
            "for customers who currently have at least one loan with status 'Default'."
        ),
        "solution": """
            SELECT DISTINCT c.customer_id, c.first_name || ' ' || c.last_name AS full_name
            FROM customers c
            JOIN loans l ON l.customer_id = c.customer_id
            WHERE l.status = 'Default'
        """,
        "ordered": False,
    },
    {
        "id": 5,
        "difficulty": "Medium",
        "topic": "Window functions",
        "prompt": (
            "For each customer, find their single largest transaction amount (by absolute "
            "value of amount). Return customer_id, transaction_id, and amount for that "
            "top transaction per customer."
        ),
        "solution": """
            WITH ranked AS (
                SELECT a.customer_id, t.transaction_id, t.amount,
                       ROW_NUMBER() OVER (
                           PARTITION BY a.customer_id
                           ORDER BY ABS(t.amount) DESC
                       ) AS rn
                FROM transactions t
                JOIN accounts a ON a.account_id = t.account_id
            )
            SELECT customer_id, transaction_id, amount
            FROM ranked
            WHERE rn = 1
        """,
        "ordered": False,
    },
    {
        "id": 6,
        "difficulty": "Medium",
        "topic": "Subqueries",
        "prompt": (
            "Find customers whose total order spend (sum of quantity * unit_price across "
            "their completed orders' order_items) exceeds $1000. Return customer_id and "
            "total_spend."
        ),
        "solution": """
            SELECT o.customer_id, SUM(oi.quantity * oi.unit_price) AS total_spend
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'Completed'
            GROUP BY o.customer_id
            HAVING SUM(oi.quantity * oi.unit_price) > 1000
        """,
        "ordered": False,
    },
    {
        "id": 7,
        "difficulty": "Hard",
        "topic": "Joins + aggregation across domains",
        "prompt": (
            "For each branch, compute the ratio of total loan principal issued to total "
            "deposit account balance held at that branch (deposits = Checking + Savings "
            "accounts). Return branch_name, total_loan_principal, total_deposit_balance, "
            "and the ratio (loan/deposit), rounded to 2 decimal places. Only include "
            "branches with nonzero deposit balance."
        ),
        "solution": """
            SELECT b.branch_name,
                   COALESCE(l.total_principal, 0) AS total_loan_principal,
                   d.total_deposit_balance,
                   ROUND(COALESCE(l.total_principal, 0) / d.total_deposit_balance, 2) AS ratio
            FROM branches b
            JOIN (
                SELECT branch_id, SUM(balance) AS total_deposit_balance
                FROM accounts
                WHERE account_type IN ('Checking', 'Savings')
                GROUP BY branch_id
                HAVING SUM(balance) > 0
            ) d ON d.branch_id = b.branch_id
            LEFT JOIN (
                SELECT branch_id, SUM(principal) AS total_principal
                FROM loans
                GROUP BY branch_id
            ) l ON l.branch_id = b.branch_id
        """,
        "ordered": False,
    },
    {
        "id": 8,
        "difficulty": "Hard",
        "topic": "Running totals (window functions)",
        "prompt": (
            "For account_id = 1, list every transaction (txn_date, amount) ordered by date, "
            "along with a running balance computed as the cumulative sum of amount over time "
            "(call it running_balance)."
        ),
        "solution": """
            SELECT txn_date, amount,
                   SUM(amount) OVER (ORDER BY txn_date, transaction_id) AS running_balance
            FROM transactions
            WHERE account_id = 1
            ORDER BY txn_date, transaction_id
        """,
        "ordered": True,
    },
]


def get_question(question_id: int):
    return next(q for q in QUESTIONS if q["id"] == question_id)
