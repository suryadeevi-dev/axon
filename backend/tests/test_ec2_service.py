"""
Unit tests for ec2_service helpers that require no AWS credentials.
"""

import pytest
from services.ec2_service import _is_ec2_id, status


class TestIsEc2Id:
    def test_valid_short(self):
        assert _is_ec2_id("i-0abc12345678") is True

    def test_valid_long(self):
        # 17-char hex suffix (Nitro instances)
        assert _is_ec2_id("i-1234567890abcdef0") is True

    def test_none(self):
        assert _is_ec2_id(None) is False

    def test_empty(self):
        assert _is_ec2_id("") is False

    def test_legacy_subprocess_id(self):
        # The exact ID that triggered the InvalidInstanceID.Malformed error in prod
        assert _is_ec2_id("iet13oey27gtdfq3ey8lk-6532622b") is False

    def test_docker_container_id(self):
        # Docker container IDs are 64-char hex, no i- prefix
        assert _is_ec2_id("a" * 64) is False

    def test_no_prefix(self):
        assert _is_ec2_id("0abc12345678") is False

    def test_uppercase_rejected(self):
        # EC2 IDs are always lowercase hex
        assert _is_ec2_id("i-0ABC12345678") is False


class TestStatusNoApiCall:
    def test_none_returns_stopped(self):
        # Must not hit EC2 API — _is_ec2_id guards it
        assert status(None) == "stopped"

    def test_invalid_id_returns_stopped(self):
        assert status("subprocess:abc123") == "stopped"

    def test_legacy_id_returns_stopped(self):
        assert status("iet13oey27gtdfq3ey8lk-6532622b") == "stopped"
