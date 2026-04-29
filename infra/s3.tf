# Agent workspace file storage — for syncing files between sessions,
# uploading results, and persisting agent artifacts beyond EC2 instance stops.
resource "aws_s3_bucket" "agent_files" {
  bucket = "${var.project}-agent-files-${data.aws_caller_identity.current.account_id}"
  tags   = { Name = "${var.project}-agent-files" }
}

resource "aws_s3_bucket_public_access_block" "agent_files" {
  bucket                  = aws_s3_bucket.agent_files.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "agent_files" {
  bucket = aws_s3_bucket.agent_files.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "agent_files" {
  bucket = aws_s3_bucket.agent_files.id

  rule {
    id     = "expire-old-artifacts"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}
