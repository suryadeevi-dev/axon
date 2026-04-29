# ── EC2 Instance Profile ───────────────────────────────────────────────────────
# Grants the SSM agent running inside each EC2 instance permission to call back
# to Systems Manager. No credentials stored on the instance.

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agent_instance" {
  name               = "${var.project}-agent-instance-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.agent_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "agent" {
  name = "${var.project}-agent-instance-profile"
  role = aws_iam_role.agent_instance.name
}


# ── Backend Service IAM User ───────────────────────────────────────────────────
# One IAM user for the Render backend covering: EC2 management, SSM command
# execution, S3 agent file storage, and DynamoDB data access.
# Replaces the manually created axon-prod DynamoDB-only user.

data "aws_iam_policy_document" "backend" {
  # EC2: launch new agent instances; tag must be applied at creation time
  statement {
    sid     = "EC2LaunchAgentInstances"
    effect  = "Allow"
    actions = ["ec2:RunInstances"]
    resources = ["arn:aws:ec2:*:*:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/Project"
      values   = [var.project]
    }
  }

  # EC2: RunInstances also needs access to the supporting resources it selects
  statement {
    sid     = "EC2LaunchSupportingResources"
    effect  = "Allow"
    actions = ["ec2:RunInstances"]
    resources = [
      "arn:aws:ec2:*::image/*",
      "arn:aws:ec2:*:*:subnet/${aws_subnet.public.id}",
      "arn:aws:ec2:*:*:security-group/${aws_security_group.agent.id}",
      "arn:aws:ec2:*:*:network-interface/*",
      "arn:aws:ec2:*:*:volume/*",
    ]
  }

  # EC2: tag resources at launch (required alongside RunInstances condition)
  statement {
    sid     = "EC2CreateTagsOnLaunch"
    effect  = "Allow"
    actions = ["ec2:CreateTags"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["RunInstances"]
    }
  }

  # EC2: lifecycle ops scoped to axon-tagged instances only
  statement {
    sid    = "EC2AgentLifecycle"
    effect = "Allow"
    actions = [
      "ec2:StartInstances",
      "ec2:StopInstances",
      "ec2:TerminateInstances",
    ]
    resources = ["arn:aws:ec2:*:*:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "ec2:ResourceTag/Project"
      values   = [var.project]
    }
  }

  # EC2: read-only describe calls (no resource scoping on Describe*)
  statement {
    sid    = "EC2Describe"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
    ]
    resources = ["*"]
  }

  # IAM: allow backend to pass the instance profile role to RunInstances
  statement {
    sid       = "IAMPassAgentRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.agent_instance.arn]
  }

  # SSM: send and check shell commands on EC2 instances via SSM Run Command
  statement {
    sid    = "SSMAgentCommands"
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
      "ssm:DescribeInstanceInformation",
    ]
    resources = ["*"]
  }

  # S3: read/write agent workspace files
  statement {
    sid    = "S3AgentFiles"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.agent_files.arn,
      "${aws_s3_bucket.agent_files.arn}/*",
    ]
  }

  # DynamoDB: users / agents / messages tables (replaces manual axon-prod policy)
  statement {
    sid    = "DynamoDBAxonTables"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = [
      "arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/axon-*",
      "arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/axon-*/index/*",
    ]
  }
}

resource "aws_iam_user" "backend" {
  name = "${var.project}-backend"
}

resource "aws_iam_user_policy" "backend" {
  name   = "${var.project}-backend-policy"
  user   = aws_iam_user.backend.name
  policy = data.aws_iam_policy_document.backend.json
}

resource "aws_iam_access_key" "backend" {
  user = aws_iam_user.backend.name
}
