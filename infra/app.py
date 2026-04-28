#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.axon_stack import AxonStack

app = cdk.App()

AxonStack(
    app,
    "AxonStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    ),
    description="AXON — autonomous AI agent platform (free tier)",
)

app.synth()
