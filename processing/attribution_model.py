import duckdb
import pandas as pd

# ─────────────────────────────────────────
# RESOURCE CATEGORIZATION ENGINE
# ─────────────────────────────────────────

RESOURCE_CATEGORY_MAP = {
    "microsoft.compute/virtualmachines":              "Compute",
    "microsoft.compute/virtualmachinescalesets":      "Compute",
    "microsoft.compute/disks":                        "Compute",
    "microsoft.containerservice/managedclusters":     "Compute",
    "microsoft.storage/storageaccounts":              "Storage",
    "microsoft.storage/storageaccounts/fileservices": "Storage",
    "microsoft.storage/storageaccounts/blobservices": "Storage",
    "microsoft.network/loadbalancers":                "Networking",
    "microsoft.network/virtualnetworks":              "Networking",
    "microsoft.network/publicipaddresses":            "Networking",
    "microsoft.network/applicationgateways":          "Networking",
    "microsoft.sql/servers/databases":                "Data Services",
    "microsoft.documentdb/databaseaccounts":          "Data Services",
    "microsoft.dbforpostgresql/servers":              "Data Services",
    "microsoft.synapse/workspaces":                   "Data Services",
}

METER_CATEGORY_MAP = {
    "compute":       "Compute",
    "storage":       "Storage",
    "networking":    "Networking",
    "network":       "Networking",
    "sql":           "Data Services",
    "database":      "Data Services",
    "data services": "Data Services",
}

def categorize_resource(resource_type: str, meter_category: str = "") -> str:
    rt_lower = str(resource_type).lower().strip()
    if rt_lower in RESOURCE_CATEGORY_MAP:
        return RESOURCE_CATEGORY_MAP[rt_lower]
    for key, category in RESOURCE_CATEGORY_MAP.items():
        if key in rt_lower:
            return category
    mc_lower = str(meter_category).lower().strip()
    for key, category in METER_CATEGORY_MAP.items():
        if key in mc_lower:
            return category
    return "Uncategorized"


# ─────────────────────────────────────────
# TEAM ATTRIBUTION ENGINE
# ─────────────────────────────────────────

RESOURCE_GROUP_RULES = {
    "rg-devops":          "DevOps",
    "rg-dataengineering": "DataEngineering",
    "rg-platform":        "Platform",
    "rg-product":         "Product",
}

def attribute_team(team_tag: str, resource_group: str) -> tuple:
    tag = str(team_tag).strip() if team_tag and str(team_tag) != 'nan' else ""
    rg  = str(resource_group).strip().lower() if resource_group else ""

    if tag and tag.startswith("team:"):
        team_name = tag.replace("team:", "").strip()
        return team_name, "high"

    for prefix, team in RESOURCE_GROUP_RULES.items():
        if rg.startswith(prefix):
            return team, "medium"

    return "Untagged", "low"


# ─────────────────────────────────────────
# RUN FULL ATTRIBUTION ON DUCKDB
# ─────────────────────────────────────────

def run_attribution(db_path: str = "data/cloudlens.db"):
    print("Running attribution model...")

    # Step 1 — Read data (read-only to avoid lock conflicts)
    read_conn = duckdb.connect(db_path, read_only=True)
    df = read_conn.execute("SELECT * FROM cleaned_costs").df()
    read_conn.close()
    print(f"Loaded {len(df)} rows from cleaned_costs")

    # Step 2 — Apply categorization
    df['category'] = df.apply(
        lambda row: categorize_resource(
            row['resource_type'],
            row.get('meter_category', '')
        ), axis=1
    )

    # Step 3 — Apply team attribution
    attribution_results = df.apply(
        lambda row: attribute_team(
            row.get('team_tag', ''),
            row.get('resource_group', '')
        ), axis=1
    )
    df['attributed_team']        = attribution_results.apply(lambda x: x[0])
    df['attribution_confidence'] = attribution_results.apply(lambda x: x[1])

    # Step 4 — Write attributed_costs table (separate write connection)
    write_conn = duckdb.connect(db_path)
    write_conn.execute("DROP TABLE IF EXISTS attributed_costs")
    write_conn.execute("CREATE TABLE attributed_costs AS SELECT * FROM df")

    # Step 5 — Print summary
    total  = len(df)
    high   = len(df[df['attribution_confidence'] == 'high'])
    medium = len(df[df['attribution_confidence'] == 'medium'])
    low    = len(df[df['attribution_confidence'] == 'low'])

    print(f"\n=== ATTRIBUTION SUMMARY ===")
    print(f"Total rows:        {total}")
    print(f"High confidence:   {high}  ({round(high/total*100,1)}%)")
    print(f"Medium confidence: {medium}  ({round(medium/total*100,1)}%)")
    print(f"Low confidence:    {low}  ({round(low/total*100,1)}%)")

    print(f"\n=== COST BY ATTRIBUTED TEAM ===")
    print(write_conn.execute("""
        SELECT attributed_team,
               ROUND(SUM(cost_inr), 2) as total_cost_inr,
               COUNT(*) as records,
               MAX(attribution_confidence) as confidence
        FROM attributed_costs
        GROUP BY attributed_team
        ORDER BY total_cost_inr DESC
    """).df())

    print(f"\n=== COST BY CATEGORY ===")
    print(write_conn.execute("""
        SELECT category,
               ROUND(SUM(cost_inr), 2) as total_cost_inr,
               COUNT(*) as records
        FROM attributed_costs
        GROUP BY category
        ORDER BY total_cost_inr DESC
    """).df())

    print(f"\n=== UNTAGGED RESOURCES (need manual review) ===")
    untagged = write_conn.execute("""
        SELECT resource_group, resource_type,
               ROUND(SUM(cost_inr), 2) as total_cost_inr
        FROM attributed_costs
        WHERE attributed_team = 'Untagged'
        GROUP BY resource_group, resource_type
        ORDER BY total_cost_inr DESC
        LIMIT 10
    """).df()
    if len(untagged) > 0:
        print(untagged)
    else:
        print("None — all resources attributed!")

    write_conn.close()
    print("\nAttribution complete!")


if __name__ == "__main__":
    run_attribution()