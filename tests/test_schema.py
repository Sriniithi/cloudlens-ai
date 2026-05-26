import pytest
import pandas as pd
import duckdb
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ingestion.generate_data import generate_billing_data
from ingestion.azure_connector import AzureCostConnector

# ─────────────────────────────────────────
# TEST 1 — CSV has correct columns
# ─────────────────────────────────────────
def test_csv_has_required_columns():
    df = pd.read_csv("data/azure_billing_raw.csv")
    required_columns = [
        "usage_date", "subscription_id", "resource_group",
        "resource_type", "service_name", "meter_category",
        "team_tag", "cost_inr", "currency"
    ]
    for col in required_columns:
        assert col in df.columns, f"Missing column: {col}"

# ─────────────────────────────────────────
# TEST 2 — No negative costs
# ─────────────────────────────────────────
def test_no_negative_costs():
    df = pd.read_csv("data/azure_billing_raw.csv")
    assert (df['cost_inr'] >= 0).all(), "Found negative cost values"

# ─────────────────────────────────────────
# TEST 3 — All 4 resource categories present
# ─────────────────────────────────────────
def test_four_resource_categories_present():
    df = pd.read_csv("data/azure_billing_raw.csv")
    expected = {"Compute", "Storage", "Networking", "Data Services"}
    actual = set(df['meter_category'].unique())
    assert expected == actual, f"Missing categories: {expected - actual}"

# ─────────────────────────────────────────
# TEST 4 — All 4 teams present
# ─────────────────────────────────────────
def test_four_teams_present():
    df = pd.read_csv("data/azure_billing_raw.csv")
    # Handle both empty string AND NaN as untagged
    tagged = df[df['team_tag'].notna() & (df['team_tag'] != '')]
    teams = set(tagged['team_tag'].str.replace('team:', '').unique())
    expected = {"DevOps", "DataEngineering", "Platform", "Product"}
    assert expected == teams, f"Missing teams: {expected - teams}"
# ─────────────────────────────────────────
# TEST 5 — Date range is 90 days
# ─────────────────────────────────────────
def test_date_range_is_90_days():
    df = pd.read_csv("data/azure_billing_raw.csv")
    df['usage_date'] = pd.to_datetime(df['usage_date'])
    day_range = (df['usage_date'].max() - df['usage_date'].min()).days
    assert day_range == 89, f"Expected 89 day range, got {day_range}"

# ─────────────────────────────────────────
# TEST 6 — Some rows are untagged (testing fallback later)
# ─────────────────────────────────────────
def test_some_rows_are_untagged():
    df = pd.read_csv("data/azure_billing_raw.csv")
    # Untagged = empty string OR NaN
    untagged = df[df['team_tag'].isna() | (df['team_tag'] == '')]
    assert len(untagged) > 0, "Expected some untagged rows for fallback testing"
# ─────────────────────────────────────────
# TEST 7 — DuckDB loads correctly
# ─────────────────────────────────────────
def test_duckdb_loads_correctly():
    # Open in read-only mode to avoid lock conflicts
    conn = duckdb.connect("data/cloudlens.db", read_only=True)
    count = conn.execute("SELECT COUNT(*) FROM raw_costs").fetchone()[0]
    conn.close()
    assert count > 0, "DuckDB raw_costs table is empty"
# ─────────────────────────────────────────
# TEST 8 — Connector returns a DataFrame
# ─────────────────────────────────────────
def test_connector_returns_dataframe():
    connector = AzureCostConnector(mode="synthetic")
    df = connector.get_cost_data(days_back=30)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0

# ─────────────────────────────────────────
# TEST 9 — Budget data has all 4 teams
# ─────────────────────────────────────────
def test_budget_data_has_all_teams():
    connector = AzureCostConnector(mode="synthetic")
    budgets = connector.get_budget_data()
    expected = {"DevOps", "DataEngineering", "Platform", "Product"}
    assert set(budgets.keys()) == expected

# ─────────────────────────────────────────
# TEST 10 — Spike exists on day 60 for DevOps Compute
# ─────────────────────────────────────────
def test_anomaly_spike_exists():
    df = pd.read_csv("data/azure_billing_raw.csv")
    df['usage_date'] = pd.to_datetime(df['usage_date'])
    spike_date = df['usage_date'].min() + pd.Timedelta(days=60)
    spike_rows = df[
        (df['usage_date'] == spike_date) &
        (df['team_tag'] == 'team:DevOps') &
        (df['meter_category'] == 'Compute')
    ]
    avg_compute_cost = df[
        (df['team_tag'] == 'team:DevOps') &
        (df['meter_category'] == 'Compute')
    ]['cost_inr'].mean()
    
    assert spike_rows['cost_inr'].values[0] > avg_compute_cost * 2, \
        "Expected a cost spike on day 60 for DevOps Compute"