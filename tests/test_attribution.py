import pytest
import pandas as pd
import duckdb
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processing.attribution_model import categorize_resource, attribute_team

DB_PATH = "data/cloudlens.db"

# ─────────────────────────────────────────
# UNIT TESTS — categorize_resource()
# ─────────────────────────────────────────

def test_compute_categorization():
    assert categorize_resource("Microsoft.Compute/virtualMachines") == "Compute"

def test_storage_categorization():
    assert categorize_resource("Microsoft.Storage/storageAccounts") == "Storage"

def test_networking_categorization():
    assert categorize_resource("Microsoft.Network/loadBalancers") == "Networking"

def test_data_services_categorization():
    assert categorize_resource("Microsoft.Sql/servers/databases") == "Data Services"

def test_fallback_to_meter_category():
    # Unknown resource_type but valid meter_category
    result = categorize_resource("Microsoft.Unknown/resource", "Compute")
    assert result == "Compute"

def test_aks_is_compute():
    assert categorize_resource(
        "Microsoft.ContainerService/managedClusters"
    ) == "Compute"

# ─────────────────────────────────────────
# UNIT TESTS — attribute_team()
# ─────────────────────────────────────────

def test_high_confidence_tag():
    team, confidence = attribute_team("team:DevOps", "rg-devops-prod")
    assert team == "DevOps"
    assert confidence == "high"

def test_medium_confidence_fallback():
    # No tag — falls back to resource_group rule
    team, confidence = attribute_team("", "rg-platform-prod")
    assert team == "Platform"
    assert confidence == "medium"

def test_low_confidence_untagged():
    # No tag, no matching resource_group
    team, confidence = attribute_team("", "rg-unknown-xyz")
    assert team == "Untagged"
    assert confidence == "low"

def test_nan_tag_treated_as_empty():
    # pandas NaN should be treated as missing tag
    team, confidence = attribute_team("nan", "rg-devops-prod")
    assert team == "DevOps"
    assert confidence == "medium"

def test_all_four_teams_attributable():
    teams_to_test = [
        ("team:DevOps",          "rg-devops-prod"),
        ("team:DataEngineering", "rg-dataengineering-prod"),
        ("team:Platform",        "rg-platform-prod"),
        ("team:Product",         "rg-product-prod"),
    ]
    expected = ["DevOps", "DataEngineering", "Platform", "Product"]
    for i, (tag, rg) in enumerate(teams_to_test):
        team, confidence = attribute_team(tag, rg)
        assert team == expected[i]
        assert confidence == "high"

# ─────────────────────────────────────────
# ACCURACY TEST — labeled test dataset
# ─────────────────────────────────────────

def test_attribution_accuracy_on_labeled_dataset():
    """
    Runs attribution on labeled test dataset.
    Target: >95% accuracy on team attribution.
    Target: 100% accuracy on category attribution.
    """
    df = pd.read_csv("data/attribution_test_dataset.csv")

    correct_team     = 0
    correct_category = 0
    total            = len(df)

    for _, row in df.iterrows():
        # Test team attribution
        team, confidence = attribute_team(
            row['team_tag'],
            row['resource_group']
        )
        if team == row['expected_team']:
            correct_team += 1

        # Test category
        category = categorize_resource(
            row['resource_type'],
            row['meter_category']
        )
        if category == row['expected_category']:
            correct_category += 1

    team_accuracy     = correct_team / total * 100
    category_accuracy = correct_category / total * 100

    print(f"\nTeam attribution accuracy:     {team_accuracy:.1f}%")
    print(f"Category attribution accuracy: {category_accuracy:.1f}%")

    assert team_accuracy >= 95, \
        f"Team accuracy {team_accuracy:.1f}% is below 95% target"
    assert category_accuracy == 100, \
        f"Category accuracy {category_accuracy:.1f}% should be 100%"

# ─────────────────────────────────────────
# INTEGRATION TEST — attributed_costs table
# ─────────────────────────────────────────

def test_attributed_costs_table_exists():
    conn = duckdb.connect(DB_PATH, read_only=True)
    tables = conn.execute("SHOW TABLES").df()['name'].tolist()
    conn.close()
    assert 'attributed_costs' in tables

def test_attributed_costs_has_no_null_teams():
    conn = duckdb.connect(DB_PATH, read_only=True)
    result = conn.execute("""
        SELECT COUNT(*) FROM attributed_costs
        WHERE attributed_team IS NULL
    """).fetchone()[0]
    conn.close()
    assert result == 0, f"Found {result} rows with null attributed_team"

def test_attribution_confidence_values_valid():
    conn = duckdb.connect(DB_PATH, read_only=True)
    confidences = conn.execute("""
        SELECT DISTINCT attribution_confidence
        FROM attributed_costs
    """).df()['attribution_confidence'].tolist()
    conn.close()
    valid = {"high", "medium", "low"}
    for c in confidences:
        assert c in valid, f"Invalid confidence value: {c}"

def test_high_confidence_above_80_percent():
    conn = duckdb.connect(DB_PATH, read_only=True)
    total = conn.execute(
        "SELECT COUNT(*) FROM attributed_costs"
    ).fetchone()[0]
    high = conn.execute("""
        SELECT COUNT(*) FROM attributed_costs
        WHERE attribution_confidence = 'high'
    """).fetchone()[0]
    conn.close()
    pct = high / total * 100
    print(f"\nHigh confidence attribution: {pct:.1f}%")
    assert pct >= 80, f"High confidence {pct:.1f}% is below 80% target"