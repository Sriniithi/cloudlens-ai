import pandas as pd
import os
from datetime import datetime, timedelta

# ─────────────────────────────────────────
# In Week 4: reads from local CSV
# In Week 15: swap get_cost_data() to call
#             Azure Cost Management API
# ─────────────────────────────────────────

class AzureCostConnector:
    
    def __init__(self, mode="synthetic"):
        """
        mode = "synthetic" → reads local CSV (Weeks 4-12)
        mode = "api"       → calls real Azure API (Week 13+)
        """
        self.mode = mode
        print(f"🔌 AzureCostConnector initialized in [{mode}] mode")

    def get_cost_data(self, days_back=30):
        """
        Returns a DataFrame of Azure cost data.
        Synthetic mode: reads from CSV
        API mode: calls Azure Cost Management API
        """
        if self.mode == "synthetic":
            return self._read_synthetic_data(days_back)
        elif self.mode == "api":
            return self._call_azure_api(days_back)

    def _read_synthetic_data(self, days_back):
        """Reads from local synthetic CSV — used during development"""
        csv_path = "data/azure_billing_raw.csv"
        
        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"Synthetic data not found at {csv_path}. "
                f"Run ingestion/generate_data.py first."
            )
        
        df = pd.read_csv(csv_path)
        df['usage_date'] = pd.to_datetime(df['usage_date'])
        
        # Filter to last N days
        cutoff = df['usage_date'].max() - timedelta(days=days_back)
        df = df[df['usage_date'] >= cutoff]
        
        print(f"✅ Loaded {len(df)} rows from synthetic data ({days_back} days)")
        return df

    def _call_azure_api(self, days_back):
        """
        Real Azure Cost Management API call
        NOTE: You will fill this in during Week 13
              when you set up your free Azure account
        """
        # This will be implemented in Week 13
        # Will use: azure-mgmt-costmanagement Python SDK
        raise NotImplementedError(
            "Azure API mode will be implemented in Week 13. "
            "Use mode='synthetic' for now."
        )

    def get_budget_data(self):
        """
        Returns budget limits per team.
        In real mode: calls Azure Budgets API
        In synthetic mode: returns hardcoded budgets
        """
        budgets = {
            "DevOps":           15000,
            "DataEngineering":  12000,
            "Platform":         18000,
            "Product":          8000,
        }
        print(f"✅ Budget data loaded for {len(budgets)} teams")
        return budgets


# ── Azure Functions entry point ───────────────────────
# This is what Azure Functions will call every day at 8am
def main(timer=None):
    """
    Azure Functions daily trigger.
    Pulls latest cost data and loads into DuckDB.
    """
    print(f"⏰ Azure Functions trigger fired at {datetime.now()}")
    
    connector = AzureCostConnector(mode="synthetic")
    df = connector.get_cost_data(days_back=1)  # just yesterday's data
    
    # Save to DuckDB (import here to avoid circular dependency)
    import duckdb
    conn = duckdb.connect("data/cloudlens.db")
    conn.execute("INSERT INTO raw_costs SELECT * FROM df")
    conn.close()
    
    print(f"✅ Daily ingestion complete: {len(df)} new rows added")


if __name__ == "__main__":
    # Test the connector locally
    connector = AzureCostConnector(mode="synthetic")
    df = connector.get_cost_data(days_back=30)
    print(df.head())
    
    budgets = connector.get_budget_data()
    print(f"\nTeam budgets: {budgets}")