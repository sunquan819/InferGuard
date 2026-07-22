"""Seed the local DataHub instance with InferGuard's demo metadata graph."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from datahub.metadata.urns import CorpUserUrn
from datahub.sdk import Dashboard, DataHubClient, Dataset, MLModel


def _connection() -> tuple[str, str]:
    server = os.environ.get("DATAHUB_GMS_URL")
    token = os.environ.get("DATAHUB_GMS_TOKEN")
    config_path = Path.home() / ".datahubenv"
    if config_path.exists() and (not server or not token):
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        gms = config.get("gms", {})
        server = server or gms.get("server")
        token = token or gms.get("token")
    if not server or not token:
        raise RuntimeError(
            "Run `datahub init` or set DATAHUB_GMS_URL and DATAHUB_GMS_TOKEN."
        )
    return server, token


def main() -> None:
    server, token = _connection()
    client = DataHubClient(server=server, token=token)
    client.test_connection()
    owner = CorpUserUrn("datahub")

    raw_orders = Dataset(
        platform="snowflake",
        name="raw.raw_orders",
        display_name="Raw Orders (schema v4)",
        description=(
            "Demo upstream table whose v4 schema renamed customer_id to "
            "customer_key, triggering the InferGuard incident."
        ),
        schema=[
            ("order_id", "string", "Order identifier"),
            ("customer_key", "string", "Renamed customer identifier"),
            ("amount", "number", "Order amount"),
            ("ordered_at", "timestamp", "Order creation time"),
        ],
        owners=[owner],
        custom_properties={"schema_version": "4", "incident_role": "root-cause"},
    )
    staged_orders = Dataset(
        platform="snowflake",
        name="staging.stg_orders",
        display_name="Staged Orders",
        description="dbt staging model that still expects customer_id.",
        schema=[
            ("order_id", "string"),
            ("customer_id", "string"),
            ("amount", "number"),
        ],
        owners=[owner],
        custom_properties={"dbt_model": "stg_orders", "status": "failing"},
    )
    features = Dataset(
        platform="snowflake",
        name="analytics.customer_ltv_features",
        display_name="Customer LTV Features",
        description="Primary production asset investigated by InferGuard.",
        schema=[
            ("customer_id", "string"),
            ("ltv_30d", "number"),
            ("ltv_90d", "number"),
            ("feature_timestamp", "timestamp"),
        ],
        owners=[owner],
        custom_properties={
            "freshness_slo_minutes": "30",
            "incident_service": "customer-ltv-features",
        },
    )
    feature_table = Dataset(
        platform="feast",
        name="customer_ltv",
        display_name="Customer LTV Feature Table",
        description="Online feature table consumed by churn-risk-v3.",
        schema=[
            ("customer_id", "string"),
            ("ltv_30d", "number"),
            ("ltv_90d", "number"),
        ],
        owners=[owner],
    )
    dashboard = Dashboard(
        platform="looker",
        name="retention-health",
        display_name="Retention Health",
        description="Executive retention dashboard in the incident blast radius.",
        input_datasets=[features],
        owners=[owner],
    )
    model = MLModel(
        id="churn-risk-v3",
        platform="mlflow",
        version="3",
        name="Churn Risk v3",
        description="Production churn model using Customer LTV features.",
        owners=[owner],
        custom_properties={
            "input_dataset_urn": str(feature_table.urn),
            "incident_role": "downstream-impact",
        },
    )

    assets = [raw_orders, staged_orders, features, feature_table, dashboard, model]
    for asset in assets:
        client.entities.upsert(asset)

    client.lineage.add_lineage(
        upstream=str(raw_orders.urn),
        downstream=str(staged_orders.urn),
    )
    client.lineage.add_lineage(
        upstream=str(staged_orders.urn),
        downstream=str(features.urn),
    )
    client.lineage.add_lineage(
        upstream=str(features.urn), downstream=str(feature_table.urn)
    )
    client.lineage.add_lineage(
        upstream=str(features.urn), downstream=str(dashboard.urn)
    )

    print(f"Seeded {len(assets)} DataHub assets at {server}")
    for asset in assets:
        print(f"- {asset.urn}")


if __name__ == "__main__":
    main()
