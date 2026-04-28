"""
AXON AWS CDK Stack — free-tier deployment

Resources:
  VPC            — 2 public subnets (no NAT gateway = no cost)
  EC2 t2.micro   — backend API + Docker daemon + agent containers
  S3             — frontend static hosting
  CloudFront     — CDN for frontend (1 TB/month free)
  DynamoDB       — users / agents / messages tables (25 GB free)
  Cognito        — user pool for optional Cognito-backed auth (50K MAU free)
  IAM            — EC2 instance role with least-privilege
  Security Groups — port 8000 for API, port 22 for SSH
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_cognito as cognito,
)
from constructs import Construct


class AxonStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ── VPC ─────────────────────────────────────────────────────────────
        vpc = ec2.Vpc(
            self, "AxonVpc",
            max_azs=2,
            nat_gateways=0,  # free tier — no NAT
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        # ── Security Groups ──────────────────────────────────────────────────
        api_sg = ec2.SecurityGroup(
            self, "ApiSG",
            vpc=vpc,
            description="AXON API security group",
            allow_all_outbound=True,
        )
        api_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(8000), "API HTTP")
        api_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH (restrict in prod)")
        api_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # ── IAM Role for EC2 ─────────────────────────────────────────────────
        ec2_role = iam.Role(
            self, "Ec2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
            ],
        )
        # DynamoDB access
        ec2_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem",
                "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan",
            ],
            resources=["*"],
        ))
        # Cognito access
        ec2_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword",
                "cognito-idp:AdminInitiateAuth", "cognito-idp:AdminGetUser",
            ],
            resources=["*"],
        ))

        # ── EC2 User Data ─────────────────────────────────────────────────────
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "#!/bin/bash",
            "set -ex",

            # Update and install Docker
            "apt-get update -y",
            "apt-get install -y docker.io git",
            "systemctl start docker",
            "systemctl enable docker",
            "usermod -aG docker ubuntu",

            # Install Python 3.11 and pip
            "apt-get install -y python3.11 python3.11-pip python3.11-venv",
            "update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1",

            # Install AWS CLI v2
            "apt-get install -y awscli",

            # Clone repo (replace with your actual repo)
            "cd /home/ubuntu",
            "git clone https://github.com/suryadeevi-dev/axon.git || true",
            "cd axon",

            # Build agent base image
            "docker build -t axon-agent-base:latest ./docker/agent-base/",

            # Install backend deps
            "cd backend",
            "python3 -m venv .venv",
            ".venv/bin/pip install --no-cache-dir -r requirements.txt",

            # Write systemd service
            "cat > /etc/systemd/system/axon-api.service << 'EOF'",
            "[Unit]",
            "Description=AXON API",
            "After=network.target docker.service",
            "[Service]",
            "User=ubuntu",
            "WorkingDirectory=/home/ubuntu/axon/backend",
            "EnvironmentFile=/home/ubuntu/axon/.env",
            "ExecStart=/home/ubuntu/axon/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2",
            "Restart=always",
            "[Install]",
            "WantedBy=multi-user.target",
            "EOF",

            "systemctl daemon-reload",
            "systemctl enable axon-api",
            "systemctl start axon-api",
        )

        # ── EC2 Instance (t2.micro = free tier 750h/month) ────────────────────
        instance = ec2.Instance(
            self, "AxonApi",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T2, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=api_sg,
            role=ec2_role,
            user_data=user_data,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(20),  # 30 GB free
                )
            ],
        )

        # ── DynamoDB Tables ───────────────────────────────────────────────────
        users_table = ddb.Table(
            self, "UsersTable",
            table_name="axon-users",
            partition_key=ddb.Attribute(name="id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,  # 25 WCU/RCU free
            removal_policy=RemovalPolicy.RETAIN,
        )
        users_table.add_global_secondary_index(
            index_name="email-index",
            partition_key=ddb.Attribute(name="email", type=ddb.AttributeType.STRING),
        )

        agents_table = ddb.Table(
            self, "AgentsTable",
            table_name="axon-agents",
            partition_key=ddb.Attribute(name="id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        agents_table.add_global_secondary_index(
            index_name="user_id-index",
            partition_key=ddb.Attribute(name="user_id", type=ddb.AttributeType.STRING),
        )

        messages_table = ddb.Table(
            self, "MessagesTable",
            table_name="axon-messages",
            partition_key=ddb.Attribute(name="id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        messages_table.add_global_secondary_index(
            index_name="agent_id-timestamp-index",
            partition_key=ddb.Attribute(name="agent_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="timestamp", type=ddb.AttributeType.STRING),
        )

        # ── S3 Bucket for Frontend ─────────────────────────────────────────────
        frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            bucket_name=f"axon-frontend-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ── CloudFront Distribution ───────────────────────────────────────────
        oac = cf.S3OriginAccessControl(self, "OAC")
        distribution = cf.Distribution(
            self, "FrontendCdn",
            default_behavior=cf.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    frontend_bucket,
                    origin_access_control=oac,
                ),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                # API requests proxy to EC2
                "/api/*": cf.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        f"{instance.instance_public_dns_name}",
                        http_port=8000,
                        protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
                    ),
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                cf.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                )
            ],
        )

        # Grant CF access to bucket
        frontend_bucket.grant_read(
            iam.ServicePrincipal("cloudfront.amazonaws.com")
        )

        # ── Cognito User Pool (optional, 50K MAU free) ───────────────────────
        user_pool = cognito.UserPool(
            self, "AxonUserPool",
            user_pool_name="axon-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=False,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        user_pool_client = user_pool.add_client(
            "AxonWebClient",
            auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
            generate_secret=False,
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "ApiInstanceId", value=instance.instance_id)
        CfnOutput(self, "ApiPublicIp", value=instance.instance_public_ip)
        CfnOutput(self, "ApiPublicDns", value=instance.instance_public_dns_name)
        CfnOutput(self, "CloudFrontUrl", value=f"https://{distribution.distribution_domain_name}")
        CfnOutput(self, "FrontendBucketName", value=frontend_bucket.bucket_name)
        CfnOutput(self, "CognitoUserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "CognitoClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "UsersTableName", value=users_table.table_name)
        CfnOutput(self, "AgentsTableName", value=agents_table.table_name)
        CfnOutput(self, "MessagesTableName", value=messages_table.table_name)
