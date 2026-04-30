variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name — used in resource names and tags"
  type        = string
  default     = "axon"
}

variable "env" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "agent_instance_type" {
  description = "EC2 instance type for agent sandboxes (t3.micro = 750 hrs/mo free tier)"
  type        = string
  default     = "t3.micro"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet (agent EC2 instances)"
  type        = string
  default     = "10.0.1.0/24"
}

