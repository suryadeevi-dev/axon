output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "Copy to Render env: EC2_SUBNET_ID"
  value       = aws_subnet.public.id
}

output "agent_security_group_id" {
  description = "Copy to Render env: EC2_SG_ID"
  value       = aws_security_group.agent.id
}

output "agent_instance_profile_name" {
  description = "Copy to Render env: EC2_INSTANCE_PROFILE"
  value       = aws_iam_instance_profile.agent.name
}

output "s3_bucket_name" {
  description = "Copy to Render env: EC2_S3_BUCKET"
  value       = aws_s3_bucket.agent_files.bucket
}

output "ubuntu_22_ami_id" {
  description = "Copy to Render env: EC2_AMI_ID"
  value       = var.ec2_ami_id
}

output "backend_iam_user" {
  description = "IAM user name for the Render backend"
  value       = aws_iam_user.backend.name
}

output "backend_access_key_id" {
  description = "Copy to Render env: AWS_ACCESS_KEY_ID"
  value       = aws_iam_access_key.backend.id
  sensitive   = true
}

output "backend_secret_access_key" {
  description = "Copy to Render env: AWS_SECRET_ACCESS_KEY"
  value       = aws_iam_access_key.backend.secret
  sensitive   = true
}
