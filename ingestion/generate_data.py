import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

# ─────────────────────────────────────────
# CONFIGURATION — edit these as you like
# ─────────────────────────────────────────

TEAMS = ["DevOps", "DataEngineering", "Platform", "Product"]
SUBSCRIPTION_ID = "sub-psiog-001"

# Resource types grouped by category
RESOURCES = {
    "Compute": [
        ("Microsoft.Compute/virtualMachines", "Virtual Machines"),
        ("Microsoft.ContainerService/managedClusters", "AKS Clusters"),
    ],
    "Storage": [
        ("Microsoft.Storage/storageAccounts", "Blob Storage"),
        ("Microsoft.Storage/storageAccounts/fileServices", "File Storage"),
    ],
    "Networking": [
        ("Microsoft.Network/loadBalancers", "Load Balancers"),
        ("Microsoft.Network/virtualNetworks", "Virtual Networks"),
    ],
    "Data Services": [
        ("Microsoft.Sql/servers/databases", "SQL Database"),
        ("Microsoft.DocumentDB/databaseAccounts", "Cosmos DB"),
    ]
}

# Base daily cost ranges per category (in INR)
BASE_COSTS = {
    "Compute":       {"DevOps": 1200, "DataEngineering": 900,  "Platform": 1500, "Product": 600},
    "Storage":       {"DevOps": 300,  "DataEngineering": 500,  "Platform": 200,  "Product": 150},
    "Networking":    {"DevOps": 200,  "DataEngineering": 150,  "Platform": 300,  "Product": 100},
    "Data Services": {"DevOps": 400,  "DataEngineering": 800,  "Platform": 350,  "Product": 250},
}

# ─────────────────────────────────────────
# GENERATE DATA
# ─────────────────────────────────────────

def generate_billing_data(days=90, spike_day=60, output_path="data/azure_billing_raw.csv"):
    
    rows = []
    start_date = datetime(2026, 1, 1)

    for day_num in range(days):
        current_date = start_date + timedelta(days=day_num)
        date_str = current_date.strftime("%Y-%m-%d")

        for team in TEAMS:
            for category, resource_list in RESOURCES.items():
                
                resource_type, service_name = random.choice(resource_list)
                resource_group = f"rg-{team.lower()}-prod"
                
                # Base cost with small daily random variation (+-15%)
                base = BASE_COSTS[category][team]
                variation = random.uniform(0.85, 1.15)
                cost = round(base * variation, 2)

                # Gradual growth over 90 days (+0.3% per day)
                growth = 1 + (day_num * 0.003)
                cost = round(cost * growth, 2)

                # SPIKE: DevOps Compute costs 4x on day 60
                # This is intentional — for anomaly detection testing in Week 14
                if day_num == spike_day and team == "DevOps" and category == "Compute":
                    cost = round(cost * 4.0, 2)
                    print(f"  ⚡ Spike injected: Day {day_num}, DevOps Compute → ₹{cost}")

                # Some rows intentionally untagged (10% chance)
                # This tests our fallback attribution logic in Week 6
                if random.random() < 0.10:
                    team_tag = ""   # untagged resource
                else:
                    team_tag = f"team:{team}"

                rows.append({
                    "usage_date":       date_str,
                    "subscription_id":  SUBSCRIPTION_ID,
                    "resource_group":   resource_group,
                    "resource_type":    resource_type,
                    "service_name":     service_name,
                    "meter_category":   category,
                    "team_tag":         team_tag,
                    "cost_inr":         cost,
                    "currency":         "INR",
                    "quantity":         round(random.uniform(1, 100), 2),
                    "unit_of_measure":  "1 Hour",
                })

    df = pd.DataFrame(rows)
    
    # Save to CSV
    os.makedirs("data", exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"\n✅ Generated {len(df)} billing rows")
    print(f"📅 Date range: {df['usage_date'].min()} → {df['usage_date'].max()}")
    print(f"👥 Teams: {df['team_tag'].unique()}")
    print(f"💰 Total cost: ₹{df['cost_inr'].sum():,.2f}")
    print(f"📁 Saved to: {output_path}")
    
    return df


if __name__ == "__main__":
    df = generate_billing_data(days=90, spike_day=60)
    print("\nFirst 5 rows:")
    print(df.head())