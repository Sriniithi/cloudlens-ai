import pytest
import duckdb
import pandas as pd
import os

DB_PATH = "data/cloudlens.db"

# ─────────────────────────────────────────
# TEST 1 — All 4 tables exist
# ─────────────────────────────────────────
def test_all_tables_exist():
    conn = duckdb.connect(DB_PATH, read_only=True)
    tables = conn.execute("SHOW TABLES").df()['name'].tolist()
    conn.close()
    expected = {"raw_costs", "cleaned_costs",
                "team_daily_costs", "monthly_summary", "budget_limits"}
    for table in expected:
        assert table in tables, f"Missing table: {table}"

# ─────────────────────────────────────────
# TEST 2 — cleaned_costs has no nulls in key columns
# ─────────────────────────────────────────
def test_no_nulls_in_key_columns():
    conn = duckdb.connect(DB_PATH, read_only=True)
    result = conn.execute("""
        SELECT COUNT(*) FROM cleaned_costs
        WHERE usage_date IS NULL
        OR cost_inr IS NULL
        OR meter_category IS NULL
    """).fetchone()[0]
    conn.close()
    assert result == 0, f"Found {result} rows with null key columns"

# ─────────────────────────────────────────
# TEST 3 — No negative costs in cleaned data
# ─────────────────────────────────────────
def test_no_negative_costs_in_cleaned():
    conn = duckdb.connect(DB_PATH, read_only=True)
    result = conn.execute("""
        SELECT COUNT(*) FROM cleaned_costs
        WHERE cost_inr < 0
    """).fetchone()[0]
    conn.close()
    assert result == 0, "Found negative costs in cleaned data"

# ─────────────────────────────────────────
# TEST 4 — All 4 teams in team_daily_costs
# ─────────────────────────────────────────
def test_all_teams_in_daily_costs():
    conn = duckdb.connect(DB_PATH, read_only=True)
    teams = conn.execute("""
        SELECT DISTINCT team FROM team_daily_costs
        WHERE team != 'Untagged'
    """).df()['team'].tolist()
    conn.close()
    expected = {"DevOps", "DataEngineering", "Platform", "Product"}
    for team in expected:
        assert team in teams, f"Missing team: {team}"

# ─────────────────────────────────────────
# TEST 5 — All 4 categories in team_daily_costs
# ─────────────────────────────────────────
def test_all_categories_in_daily_costs():
    conn = duckdb.connect(DB_PATH, read_only=True)
    cats = conn.execute("""
        SELECT DISTINCT resource_category FROM team_daily_costs
    """).df()['resource_category'].tolist()
    conn.close()
    expected = {"Compute", "Storage", "Networking", "Data Services"}
    for cat in expected:
        assert cat in cats, f"Missing category: {cat}"

# ─────────────────────────────────────────
# TEST 6 — Budget limits has all 4 teams
# ─────────────────────────────────────────
def test_budget_limits_complete():
    conn = duckdb.connect(DB_PATH, read_only=True)
    teams = conn.execute("""
        SELECT team FROM budget_limits
    """).df()['team'].tolist()
    conn.close()
    expected = {"DevOps", "DataEngineering", "Platform", "Product"}
    assert set(teams) == expected

# ─────────────────────────────────────────
# TEST 7 — monthly_summary has 3 months
# ─────────────────────────────────────────
def test_monthly_summary_has_three_months():
    conn = duckdb.connect(DB_PATH, read_only=True)
    months = conn.execute("""
        SELECT DISTINCT month FROM monthly_summary
        ORDER BY month
    """).df()['month'].tolist()
    conn.close()
    assert len(months) == 3, f"Expected 3 months, got {len(months)}: {months}"

# ─────────────────────────────────────────
# TEST 8 — team_daily_costs totals match cleaned_costs
# ─────────────────────────────────────────
def test_cost_totals_match():
    conn = duckdb.connect(DB_PATH, read_only=True)
    total_cleaned = conn.execute(
        "SELECT ROUND(SUM(cost_inr), 0) FROM cleaned_costs"
    ).fetchone()[0]
    total_daily = conn.execute(
        "SELECT ROUND(SUM(total_cost_inr), 0) FROM team_daily_costs"
    ).fetchone()[0]
    conn.close()
    assert total_cleaned == total_daily, \
        f"Cost mismatch: cleaned={total_cleaned}, daily={total_daily}"