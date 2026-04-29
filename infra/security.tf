# Agent instances are command-execution sandboxes — no inbound traffic allowed.
# SSM connects outbound (HTTPS) to the Systems Manager endpoint, so no inbound
# rules are needed. This means no public SSH exposure, ever.
resource "aws_security_group" "agent" {
  name        = "${var.project}-agent-sg"
  description = "Axon agent EC2 - outbound-only (SSM + internet for package installs)"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound: SSM endpoint, apt/pip, agent tasks"
  }

  tags = { Name = "${var.project}-agent-sg" }
}
