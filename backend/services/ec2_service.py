"""
EC2 agent compute service.

Each agent maps to one EC2 instance. Command execution goes through SSM Run
Command — no SSH keys, no open inbound ports. The SSM agent inside the instance
connects outbound to the Systems Manager endpoint.

Instance lifecycle:
  provision(agent_id)      → RunInstances → wait SSM ready → return instance_id
  exec_command(id, cmd)    → SSM SendCommand → poll GetCommandInvocation
  start(instance_id)       → StartInstances → wait SSM ready
  stop(instance_id)        → StopInstances  (EBS persists, compute hours saved)
  terminate(instance_id)   → TerminateInstances (agent deleted)
  status(instance_id)      → DescribeInstances state

S3 helpers:
  upload_file / download_file / list_s3_files  — agent workspace file sync
"""

import logging
import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

_REGION           = os.getenv("AWS_REGION", "us-east-1")
_INSTANCE_TYPE    = os.getenv("EC2_INSTANCE_TYPE", "t3.micro")
_AMI_ID           = os.getenv("EC2_AMI_ID", "")
_SUBNET_ID        = os.getenv("EC2_SUBNET_ID", "")
_SG_ID            = os.getenv("EC2_SG_ID", "")
_INSTANCE_PROFILE = os.getenv("EC2_INSTANCE_PROFILE", "axon-agent-instance-profile")
_S3_BUCKET        = os.getenv("EC2_S3_BUCKET", "")

_PROVISION_TIMEOUT = int(os.getenv("EC2_PROVISION_TIMEOUT", "300"))
_COMMAND_TIMEOUT   = int(os.getenv("EC2_COMMAND_TIMEOUT", "30"))
_SSM_POLL_INTERVAL = 2  # seconds between SSM status polls

_USERDATA = """#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nodejs npm git curl wget unzip jq build-essential
id axon 2>/dev/null || useradd -m -s /bin/bash axon
mkdir -p /home/axon/workspace
chown -R axon:axon /home/axon
echo "AXON agent bootstrap complete at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> /var/log/axon-init.log
"""


def ec2_available() -> bool:
    return bool(
        os.getenv("EC2_ENABLED", "").lower() == "true"
        and _AMI_ID
        and _SUBNET_ID
        and _SG_ID
        and os.getenv("AWS_ACCESS_KEY_ID")
    )


def _ec2():
    return boto3.client("ec2", region_name=_REGION)


def _ssm():
    return boto3.client("ssm", region_name=_REGION)


def _s3():
    return boto3.client("s3", region_name=_REGION)


# ── Instance lifecycle ─────────────────────────────────────────────────────────

def provision(agent_id: str, existing_instance_id: Optional[str] = None) -> str:
    """
    Return a running instance ID for the agent.
    Reconnects to an existing stopped instance before launching a new one.
    """
    if existing_instance_id:
        current = status(existing_instance_id)
        if current == "running":
            return existing_instance_id
        if current == "stopped":
            log.info("EC2 starting stopped instance %s for agent %s", existing_instance_id, agent_id)
            _ec2().start_instances(InstanceIds=[existing_instance_id])
            _wait_for_ssm(existing_instance_id)
            return existing_instance_id
        # terminated / unknown — fall through to launch a new one

    resp = _ec2().run_instances(
        ImageId=_AMI_ID,
        InstanceType=_INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        SubnetId=_SUBNET_ID,
        SecurityGroupIds=[_SG_ID],
        IamInstanceProfile={"Name": _INSTANCE_PROFILE},
        UserData=_USERDATA,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name",    "Value": f"axon-agent-{agent_id[:12]}"},
                {"Key": "Project", "Value": "axon"},
                {"Key": "AgentId", "Value": agent_id},
            ],
        }],
        BlockDeviceMappings=[{
            "DeviceName": "/dev/sda1",
            "Ebs": {
                "VolumeSize": 8,            # GB — free tier: 30 GB total across all volumes
                "VolumeType": "gp3",
                "DeleteOnTermination": True,
            },
        }],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    log.info("EC2 instance launched: %s for agent %s", instance_id, agent_id)
    _wait_for_ssm(instance_id)
    return instance_id


def _wait_for_ssm(instance_id: str, timeout: int = _PROVISION_TIMEOUT):
    """Block until the SSM agent on the instance registers with Systems Manager."""
    deadline = time.monotonic() + timeout
    log.info("Waiting for SSM registration on %s (up to %ds)", instance_id, timeout)
    while time.monotonic() < deadline:
        try:
            resp = _ssm().describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
            )
            if resp.get("InstanceInformationList"):
                log.info("SSM agent ready on %s", instance_id)
                return
        except ClientError:
            pass
        time.sleep(_SSM_POLL_INTERVAL)
    raise TimeoutError(f"SSM agent on {instance_id} did not register within {timeout}s")


def start(instance_id: str) -> str:
    _ec2().start_instances(InstanceIds=[instance_id])
    _wait_for_ssm(instance_id)
    return instance_id


def stop(instance_id: str):
    try:
        _ec2().stop_instances(InstanceIds=[instance_id])
        log.info("EC2 instance stopped: %s", instance_id)
    except ClientError as e:
        log.warning("EC2 stop %s: %s", instance_id, e)


def terminate(instance_id: str):
    try:
        _ec2().terminate_instances(InstanceIds=[instance_id])
        log.info("EC2 instance terminated: %s", instance_id)
    except ClientError as e:
        log.warning("EC2 terminate %s: %s", instance_id, e)


def status(instance_id: str) -> str:
    try:
        resp = _ec2().describe_instances(InstanceIds=[instance_id])
        reservations = resp.get("Reservations", [])
        if not reservations:
            return "stopped"
        state = reservations[0]["Instances"][0]["State"]["Name"]
        return {
            "running":       "running",
            "pending":       "starting",
            "stopped":       "stopped",
            "stopping":      "stopped",
            "shutting-down": "stopped",
            "terminated":    "stopped",
        }.get(state, "stopped")
    except ClientError:
        return "stopped"


# ── Command execution via SSM ──────────────────────────────────────────────────

def exec_command(
    instance_id: str,
    command: str,
    timeout: int = _COMMAND_TIMEOUT,
) -> tuple[int, str]:
    """Run a shell command on the EC2 instance via SSM Run Command."""
    try:
        resp = _ssm().send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [f"cd /home/axon/workspace && {command}"]},
            TimeoutSeconds=min(timeout + 10, 3600),
        )
        command_id = resp["Command"]["CommandId"]
        return _poll_command(instance_id, command_id, timeout)
    except ClientError as e:
        return 1, str(e)


def _poll_command(instance_id: str, command_id: str, timeout: int) -> tuple[int, str]:
    deadline = time.monotonic() + timeout + 15  # buffer for SSM scheduling overhead
    ssm = _ssm()
    while time.monotonic() < deadline:
        time.sleep(_SSM_POLL_INTERVAL)
        try:
            result = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            state = result["StatusDetails"]
            if state in ("Pending", "InProgress", "Delayed"):
                continue
            stdout = result.get("StandardOutputContent", "")
            stderr = result.get("StandardErrorContent", "")
            output = (stdout + ("\n" + stderr if stderr.strip() else "")).strip()
            exit_code = 0 if state == "Success" else 1
            return exit_code, output or "(no output)"
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        except ClientError as e:
            return 1, str(e)
    return 1, f"Command timed out after {timeout}s"


# ── S3 file storage ────────────────────────────────────────────────────────────

def upload_file(agent_id: str, local_path: str, key: str) -> str:
    """Upload a local file to the agent's S3 prefix. Returns the S3 URI."""
    if not _S3_BUCKET:
        raise RuntimeError("EC2_S3_BUCKET not configured")
    s3_key = f"agents/{agent_id}/{key}"
    _s3().upload_file(local_path, _S3_BUCKET, s3_key)
    return f"s3://{_S3_BUCKET}/{s3_key}"


def download_file(agent_id: str, key: str, local_path: str):
    if not _S3_BUCKET:
        raise RuntimeError("EC2_S3_BUCKET not configured")
    _s3().download_file(_S3_BUCKET, f"agents/{agent_id}/{key}", local_path)


def list_s3_files(agent_id: str) -> list[dict]:
    if not _S3_BUCKET:
        return []
    prefix = f"agents/{agent_id}/"
    try:
        resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
        return [
            {
                "key":           obj["Key"].removeprefix(prefix),
                "size":          obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
            for obj in resp.get("Contents", [])
        ]
    except ClientError:
        return []
