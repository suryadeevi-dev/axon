"""
Run once to create the three DynamoDB tables AXON needs.
Usage: python scripts/create_dynamo_tables.py

Requires: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION in env
          (or a configured ~/.aws/credentials profile)
"""
import boto3
import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.client("dynamodb", region_name=REGION)


def create_table(name: str, pk: str, gsi_list: list):
    try:
        attrs = {pk}
        for gsi in gsi_list:
            attrs.add(gsi["key"])
            if "sort" in gsi:
                attrs.add(gsi["sort"])

        attribute_defs = [{"AttributeName": a, "AttributeType": "S"} for a in attrs]

        gsi_defs = []
        for gsi in gsi_list:
            keys = [{"AttributeName": gsi["key"], "KeyType": "HASH"}]
            if "sort" in gsi:
                keys.append({"AttributeName": gsi["sort"], "KeyType": "RANGE"})
            gsi_defs.append({
                "IndexName": gsi["name"],
                "KeySchema": keys,
                "Projection": {"ProjectionType": "ALL"},
            })

        kwargs = {
            "TableName": name,
            "KeySchema": [{"AttributeName": pk, "KeyType": "HASH"}],
            "AttributeDefinitions": attribute_defs,
            "BillingMode": "PAY_PER_REQUEST",
        }
        if gsi_defs:
            kwargs["GlobalSecondaryIndexes"] = gsi_defs

        dynamodb.create_table(**kwargs)
        print(f"  [OK] {name} - created")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"  [--] {name} - already exists, skipped")
    except Exception as e:
        print(f"  [ERR] {name} - error: {e}")
        sys.exit(1)


print(f"Creating AXON DynamoDB tables in {REGION}...")

create_table("axon-users",    pk="id", gsi_list=[{"name": "email-index", "key": "email"}])
create_table("axon-agents",   pk="id", gsi_list=[{"name": "user_id-index", "key": "user_id"}])
create_table("axon-messages", pk="id", gsi_list=[{"name": "agent_id-timestamp-index", "key": "agent_id", "sort": "timestamp"}])

print("\nDone. Add these to Render environment:")
print("  AWS_ACCESS_KEY_ID=<axon-render-prod key>")
print("  AWS_SECRET_ACCESS_KEY=<axon-render-prod secret>")
print(f"  AWS_REGION={REGION}")
