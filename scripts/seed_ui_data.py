"""
PathWise AI — UI Seed Data Script
Inserts 1 admin + 8 SME business owner user accounts with realistic demo data.
Run: python scripts/seed_ui_data.py
"""

import os, sys, bcrypt, json, random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Use the project's DB module for automatic PG/SQLite fallback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.db import get_engine
engine = get_engine()

# ─── Account definitions ─────────────────────────────────────────────────────

ADMIN_ACCOUNT = {
    "id": "admin-001",
    "name": "Vineeth Reddy (Super Admin)",
    "email": "admin@pathwise.ai",
    "password": "Admin@PathWise2026",
    "role": "SUPER_ADMIN",
    "company": "PathWise AI",
    "avatar_initials": "VA",
    "plan": None
}

USER_ACCOUNTS = [
    {
        "id": "user-001",
        "name": "Marcus Rivera",
        "email": "marcus@riveralogistics.com",
        "password": "Rivera@2026",
        "role": "BUSINESS_OWNER",
        "company": "Rivera Logistics LLC",
        "industry": "Logistics",
        "sites": ["Dallas HQ", "Houston Depot"],
        "plan": "professional",
        "mrr": 149.00,
        "avatar_initials": "MR"
    },
    {
        "id": "user-002",
        "name": "Priya Nair",
        "email": "priya@nairmedical.com",
        "password": "NairMed@2026",
        "role": "BUSINESS_OWNER",
        "company": "Nair Medical Group",
        "industry": "Healthcare",
        "sites": ["Main Clinic", "Lab Annex", "Pharmacy"],
        "plan": "enterprise",
        "mrr": 299.00,
        "avatar_initials": "PN"
    },
    {
        "id": "user-003",
        "name": "DeShawn Carter",
        "email": "deshawn@carterretail.com",
        "password": "Carter@2026",
        "role": "BUSINESS_OWNER",
        "company": "Carter Retail Group",
        "industry": "Retail",
        "sites": ["Store A", "Store B", "Warehouse"],
        "plan": "starter",
        "mrr": 49.00,
        "avatar_initials": "DC"
    },
    {
        "id": "user-004",
        "name": "Sofia Morales",
        "email": "sofia@moralesacademy.edu",
        "password": "Sofia@2026",
        "role": "BUSINESS_OWNER",
        "company": "Morales Academy",
        "industry": "Education",
        "sites": ["Main Campus", "Sports Complex"],
        "plan": "professional",
        "mrr": 149.00,
        "avatar_initials": "SM"
    },
    {
        "id": "user-005",
        "name": "Kenji Tanaka",
        "email": "kenji@tanakafab.com",
        "password": "Tanaka@2026",
        "role": "BUSINESS_OWNER",
        "company": "Tanaka Fabrications",
        "industry": "Manufacturing",
        "sites": ["Factory Floor", "Office Block"],
        "plan": "professional",
        "mrr": 149.00,
        "avatar_initials": "KT"
    },
    {
        "id": "user-006",
        "name": "Amara Osei",
        "email": "amara@oseifinance.com",
        "password": "Amara@2026",
        "role": "BUSINESS_OWNER",
        "company": "Osei Financial Services",
        "industry": "Finance",
        "sites": ["Main Office", "Branch East"],
        "plan": "enterprise",
        "mrr": 299.00,
        "avatar_initials": "AO"
    },
    {
        "id": "user-007",
        "name": "Elena Petrov",
        "email": "elena@petrovhotel.com",
        "password": "Elena@2026",
        "role": "BUSINESS_OWNER",
        "company": "Petrov Hospitality Group",
        "industry": "Hospitality",
        "sites": ["Downtown Hotel", "Airport Hotel"],
        "plan": "starter",
        "mrr": 49.00,
        "avatar_initials": "EP"
    },
    {
        "id": "user-008",
        "name": "Tobias Bauer",
        "email": "tobias@bauertech.io",
        "password": "Bauer@2026",
        "role": "BUSINESS_OWNER",
        "company": "Bauer Tech Solutions",
        "industry": "Technology",
        "sites": ["Dev Office", "Server Room"],
        "plan": "enterprise",
        "mrr": 299.00,
        "avatar_initials": "TB"
    }
]

PLANS = {
    "starter":      {"name": "Starter",      "price": 49.00,  "sites": 2,  "links_per_site": 2, "features": ["basic_dashboard","email_alerts","csv_export"]},
    "professional": {"name": "Professional", "price": 149.00, "sites": 5,  "links_per_site": 4, "features": ["full_dashboard","lstm_forecasting","ibn","sandbox","pdf_export","priority_support"]},
    "enterprise":   {"name": "Enterprise",   "price": 299.00, "sites": 20, "links_per_site": 6, "features": ["full_dashboard","lstm_forecasting","ibn","sandbox","pdf_export","dedicated_support","hipaa_audit","multi_site_analytics"]},
}

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()

def seed():
    with engine.connect() as conn:
        # Create tables individually (SQLite can't execute multiple DDL in one text())
        tables = [
            """CREATE TABLE IF NOT EXISTS app_users (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                email VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                role VARCHAR NOT NULL DEFAULT 'BUSINESS_OWNER',
                company VARCHAR,
                industry VARCHAR,
                avatar_initials VARCHAR(3),
                is_active BOOLEAN DEFAULT 1,
                failed_attempts INT DEFAULT 0,
                locked_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS subscriptions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                plan_id VARCHAR NOT NULL,
                plan_name VARCHAR NOT NULL,
                status VARCHAR DEFAULT 'active',
                monthly_price REAL,
                billing_cycle VARCHAR DEFAULT 'monthly',
                start_date DATE DEFAULT CURRENT_DATE,
                next_billing_date DATE,
                payment_method VARCHAR DEFAULT 'card_ending_4242',
                card_last4 VARCHAR(4) DEFAULT '4242',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS sites (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                name VARCHAR NOT NULL,
                location VARCHAR,
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS support_tickets (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                subject VARCHAR NOT NULL,
                description TEXT,
                priority VARCHAR DEFAULT 'medium',
                status VARCHAR DEFAULT 'open',
                category VARCHAR DEFAULT 'general',
                admin_response TEXT,
                resolved_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS invoices (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                subscription_id VARCHAR,
                amount REAL,
                status VARCHAR DEFAULT 'paid',
                period_start DATE,
                period_end DATE,
                issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS lstm_model_configs (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                description TEXT,
                sequence_length INT DEFAULT 60,
                hidden_units INT DEFAULT 128,
                num_layers INT DEFAULT 2,
                dropout REAL DEFAULT 0.2,
                learning_rate REAL DEFAULT 0.001,
                batch_size INT DEFAULT 32,
                epochs INT DEFAULT 100,
                is_active BOOLEAN DEFAULT 0,
                accuracy REAL,
                mae_latency REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
        for ddl in tables:
            conn.execute(text(ddl))

        # Insert accounts (INSERT OR IGNORE for SQLite compat)
        all_accounts = [ADMIN_ACCOUNT] + USER_ACCOUNTS
        for acc in all_accounts:
            conn.execute(text("""
            INSERT OR IGNORE INTO app_users (id, name, email, password_hash, role, company, industry, avatar_initials)
            VALUES (:id, :name, :email, :ph, :role, :company, :industry, :ai)
            """), {"id": acc["id"], "name": acc["name"], "email": acc["email"],
                   "ph": hash_password(acc["password"]), "role": acc["role"],
                   "company": acc.get("company"), "industry": acc.get("industry"),
                   "ai": acc.get("avatar_initials", acc["name"][:2].upper())})

        # Insert subscriptions and sites for each user
        import uuid
        for acc in USER_ACCOUNTS:
            plan = acc["plan"]
            plan_meta = PLANS[plan]
            sub_id = f"sub-{acc['id']}"
            conn.execute(text("""
            INSERT OR IGNORE INTO subscriptions (id, user_id, plan_id, plan_name, monthly_price, next_billing_date)
            VALUES (:id, :uid, :pid, :pname, :price, :nbd)
            """), {"id": sub_id, "uid": acc["id"], "pid": plan, "pname": plan_meta["name"],
                   "price": plan_meta["price"],
                   "nbd": (datetime.now() + timedelta(days=30)).date()})

            for i, site_name in enumerate(acc["sites"]):
                site_id = f"site-{acc['id']}-{i+1}"
                conn.execute(text("""
                INSERT OR IGNORE INTO sites (id, user_id, name, location)
                VALUES (:id, :uid, :name, :loc)
                """), {"id": site_id, "uid": acc["id"], "name": site_name,
                       "loc": f"{acc['company']} — {site_name}"})

            # Generate 3 invoices per user
            for m in range(3):
                inv_id = f"inv-{acc['id']}-{m+1}"
                period_start = datetime.now().date() - timedelta(days=30*(m+1))
                period_end   = datetime.now().date() - timedelta(days=30*m)
                conn.execute(text("""
                INSERT OR IGNORE INTO invoices (id, user_id, subscription_id, amount, period_start, period_end)
                VALUES (:id, :uid, :sid, :amt, :ps, :pe)
                """), {"id": inv_id, "uid": acc["id"], "sid": sub_id,
                       "amt": plan_meta["price"], "ps": period_start, "pe": period_end})

        # Insert sample tickets
        sample_tickets = [
            ("ticket-001", "user-001", "Fiber link showing false degradation alerts",
             "Getting alerts every 5 minutes but link is healthy", "high", "bug"),
            ("ticket-002", "user-003", "How to export telemetry as CSV?",
             "Cannot find the export button on dashboard", "low", "how_to"),
            ("ticket-004", "user-002", "HIPAA audit log export format",
             "Need the audit log in a specific format for compliance", "medium", "compliance"),
            ("ticket-005", "user-006", "Upgrade plan from Enterprise to custom",
             "We need more than 20 sites", "medium", "billing"),
        ]
        for t in sample_tickets:
            conn.execute(text("""
            INSERT OR IGNORE INTO support_tickets (id, user_id, subject, description, priority, category)
            VALUES (:id, :uid, :sub, :desc, :pri, :cat)
            """), {"id": t[0], "uid": t[1], "sub": t[2], "desc": t[3], "pri": t[4], "cat": t[5]})

        # Insert LSTM model configs
        lstm_models = [
            ("lstm-v1", "LSTM v1 — Baseline", "Original production model", 60, 64, 2, 0.2, 0.001, 32, 100, True, 90.5, 6.94),
            ("lstm-v2", "LSTM v2 — Deep", "Deeper architecture with 4 layers", 90, 128, 4, 0.3, 0.0005, 64, 150, False, 92.1, 5.41),
            ("lstm-v3", "LSTM v3 — Experimental", "Bidirectional LSTM experiment", 60, 256, 2, 0.25, 0.001, 32, 200, False, None, None),
        ]
        for m in lstm_models:
            conn.execute(text("""
            INSERT OR IGNORE INTO lstm_model_configs (id,name,description,sequence_length,hidden_units,num_layers,
                dropout,learning_rate,batch_size,epochs,is_active,accuracy,mae_latency)
            VALUES (:id,:name,:desc,:sl,:hu,:nl,:do,:lr,:bs,:ep,:ia,:acc,:mae)
            """), {"id": m[0],"name": m[1],"desc": m[2],"sl": m[3],"hu": m[4],"nl": m[5],
                   "do": m[6],"lr": m[7],"bs": m[8],"ep": m[9],"ia": m[10],"acc": m[11],"mae": m[12]})

        conn.commit()
        print("Seed data inserted successfully.")
        print("\nLogin credentials:")
        print(f"  Admin:   admin@pathwise.ai         / Admin@PathWise2026")
        for u in USER_ACCOUNTS:
            print(f"  User:    {u['email']:<35} / {u['password']}")

if __name__ == "__main__":
    seed()
