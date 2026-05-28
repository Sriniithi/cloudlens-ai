import duckdb
import pandas as pd
import os

def setup_duckdb_schema(
    clean_csv="data/azure_billing_clean.csv",
    db_path="data/cloudlens.db"
):
    print("Setting up DuckDB schema...")
    conn = duckdb.connect(db_path)

    # ── Table 1: cleaned_costs (main table)
    conn.execute("DROP TABLE IF EXISTS cleaned_costs")
    conn.execute(f"""
        CREATE TABLE cleaned_costs AS
        SELECT * FROM read_csv_auto('{clean_csv}')
    """)
    count = conn.execute("SELECT COUNT(*) FROM cleaned_costs").fetchone()[0]
    print(f"cleaned_costs: {count} rows")

    # ── Table 2: team_daily_costs (aggregated by team + day)
    conn.execute("DROP TABLE IF EXISTS team_daily_costs")
    conn.execute("""
        CREATE TABLE team_daily_costs AS
        SELECT
            usage_date,
            replace(team_tag, 'team:', '') as team,
            meter_category as resource_category,
            ROUND(SUM(cost_inr), 2) as total_cost_inr,
            COUNT(*) as resource_count
        FROM cleaned_costs
        GROUP BY usage_date, team_tag, meter_category
        ORDER BY usage_date, team
    """)
    count2 = conn.execute("SELECT COUNT(*) FROM team_daily_costs").fetchone()[0]
    print(f"team_daily_costs: {count2} rows")

    # ── Table 3: monthly_summary (aggregated by team + month)
    conn.execute("DROP TABLE IF EXISTS monthly_summary")
    conn.execute("""
        CREATE TABLE monthly_summary AS
        SELECT
            STRFTIME(usage_date, '%Y-%m') as month,
            replace(team_tag, 'team:', '') as team,
            meter_category as resource_category,
            ROUND(SUM(cost_inr), 2) as total_cost_inr,
            COUNT(*) as resource_count
        FROM cleaned_costs
        GROUP BY month, team_tag, meter_category
        ORDER BY month, team
    """)
    count3 = conn.execute("SELECT COUNT(*) FROM monthly_summary").fetchone()[0]
    print(f"monthly_summary: {count3} rows")

    # ── Table 4: budget_limits
    conn.execute("DROP TABLE IF EXISTS budget_limits")
    conn.execute("""
        CREATE TABLE budget_limits (
            team VARCHAR,
            monthly_budget_inr DOUBLE,
            alert_threshold_80 DOUBLE,
            alert_threshold_100 DOUBLE
        )
    """)
    conn.execute("""
        INSERT INTO budget_limits VALUES
            ('DevOps',          15000, 12000, 15000),
            ('DataEngineering', 12000,  9600, 12000),
            ('Platform',        18000, 14400, 18000),
            ('Product',          8000,  6400,  8000)
    """)
    print(f"budget_limits: 4 rows")

    # ── Show all tables
    print("\n=== ALL TABLES IN DuckDB ===")
    print(conn.execute("SHOW TABLES").df())

    # ── Show sample from team_daily_costs
    print("\n=== SAMPLE: team_daily_costs ===")
    print(conn.execute("""
        SELECT * FROM team_daily_costs
        LIMIT 8
    """).df())

    # ── Show monthly summary
    print("\n=== MONTHLY SUMMARY ===")
    print(conn.execute("""
        SELECT month, team,
               SUM(total_cost_inr) as monthly_total
        FROM monthly_summary
        GROUP BY month, team
        ORDER BY month, monthly_total DESC
    """).df())

    conn.close()
    print("\nDuckDB schema setup complete!")


if __name__ == "__main__":
    setup_duckdb_schema()