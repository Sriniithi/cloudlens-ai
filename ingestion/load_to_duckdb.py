import duckdb
import pandas as pd
import os

def load_csv_to_duckdb(
    csv_path="data/azure_billing_raw.csv",
    db_path="data/cloudlens.db"
):
    print(f"📂 Loading {csv_path} into DuckDB...")
    
    # Connect to DuckDB (creates the file if it doesn't exist)
    conn = duckdb.connect(db_path)

    # Drop table if it already exists (safe to re-run)
    conn.execute("DROP TABLE IF EXISTS raw_costs")

    # Create table directly from CSV
    conn.execute(f"""
        CREATE TABLE raw_costs AS 
        SELECT * FROM read_csv_auto('{csv_path}')
    """)

    # Verify it loaded correctly
    count = conn.execute("SELECT COUNT(*) FROM raw_costs").fetchone()[0]
    print(f"✅ Loaded {count} rows into raw_costs table")

    # Show sample
    print("\n📊 Sample data (first 3 rows):")
    print(conn.execute("SELECT * FROM raw_costs LIMIT 3").df())

    # Show cost by team
    print("\n💰 Total cost by team:")
    print(conn.execute("""
        SELECT 
            CASE WHEN team_tag = '' THEN 'Untagged' 
                 ELSE replace(team_tag, 'team:', '') 
            END as team,
            ROUND(SUM(cost_inr), 2) as total_cost_inr,
            COUNT(*) as num_records
        FROM raw_costs
        GROUP BY team_tag
        ORDER BY total_cost_inr DESC
    """).df())

    # Show cost by category
    print("\n📦 Total cost by resource category:")
    print(conn.execute("""
        SELECT 
            meter_category,
            ROUND(SUM(cost_inr), 2) as total_cost_inr
        FROM raw_costs
        GROUP BY meter_category
        ORDER BY total_cost_inr DESC
    """).df())

    conn.close()
    print(f"\n✅ DuckDB saved at: {db_path}")


if __name__ == "__main__":
    load_csv_to_duckdb()