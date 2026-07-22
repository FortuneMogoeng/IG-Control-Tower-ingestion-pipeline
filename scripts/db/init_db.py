#!/usr/bin/env python3
"""Initialize the ig-control-tower SQLite database.

Usage: python scripts/init_db.py
Creates ~/.claude/data/ig-control-tower.db if it doesn't exist.
Safe to run multiple times — uses IF NOT EXISTS.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.environ.get("IG_CONTROL_TOWER_DB_PATH",
                              Path.home() / ".claude" / "data" / "ig-control-tower.db"))
DB_DIR = DB_PATH.parent


def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS generic_opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opportunity_id TEXT UNIQUE,
        name TEXT NOT NULL,
        dimension TEXT NOT NULL,
        theme TEXT,
        description TEXT,
        build_type TEXT,
        applicable_sectors TEXT,
        applicable_divisions TEXT,
        technology_types TEXT,
        technology_vendors TEXT,
        platforms TEXT,
        approach TEXT,
        integrations TEXT,
        data_requirements TEXT,
        primary_evidence_company TEXT,
        primary_evidence_title TEXT,
        primary_evidence_outcome TEXT,
        primary_evidence_year TEXT,
        additional_evidence TEXT,
        sources TEXT,
        complexity TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id TEXT UNIQUE,
        company_name TEXT NOT NULL,
        company_slug TEXT NOT NULL,
        generic_opportunity_id INTEGER REFERENCES generic_opportunities(id),
        dimension TEXT NOT NULL,
        theme TEXT,
        value_amount_gbp REAL,
        value_methodology TEXT,
        value_impact_pct REAL,
        quantified_benefits TEXT,
        qualitative_benefits TEXT,
        value_proposition TEXT,
        cost_range TEXT,
        cost_licensing REAL,
        cost_development REAL,
        cost_integration REAL,
        time_to_build TEXT,
        time_to_roi TEXT,
        implementation_phases TEXT,
        key_delivery_components TEXT,
        complexity TEXT,
        company_context TEXT,
        technology_specifics TEXT,
        change_management TEXT,
        risks TEXT,
        process_description TEXT,
        score_value_impact REAL,
        score_data_readiness REAL,
        score_feasibility REAL,
        score_strategic_alignment REAL,
        score_weighted REAL,
        regulatory_flags TEXT,
        compliance_risk TEXT,
        required_approvals TEXT,
        dependencies TEXT,
        integration_group TEXT,
        peer_gap_flag INTEGER DEFAULT 0,
        is_novel INTEGER DEFAULT 0,
        company_page_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        company_slug TEXT UNIQUE NOT NULL,
        annual_revenue_gbp REAL,
        employee_count INTEGER,
        sector TEXT,
        regions TEXT,
        tech_stack TEXT,
        ai_maturity TEXT,
        departments TEXT,
        competitors TEXT,
        company_page_url TEXT,
        logo_url TEXT,
        brand_colors TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create indexes for common queries
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_generic_sectors
    ON generic_opportunities(applicable_sectors)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_generic_dimension
    ON generic_opportunities(dimension)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_analyses_company
    ON company_analyses(company_slug)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_analyses_score
    ON company_analyses(score_weighted DESC)
    """)

    conn.commit()
    conn.close()

    print(f"Database initialized at: {DB_PATH}")
    existing = sqlite3.connect(str(DB_PATH))
    c = existing.cursor()
    c.execute("SELECT COUNT(*) FROM generic_opportunities")
    gen_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM company_analyses")
    ana_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM company_profiles")
    prof_count = c.fetchone()[0]
    existing.close()
    print(f"Records: {gen_count} generic opportunities, {ana_count} analyses, {prof_count} profiles")


if __name__ == "__main__":
    init_db()
