#!/usr/bin/env bash
# AXON — full production deployment script
# Usage: AWS_PROFILE=your-profile ./scripts/deploy.sh

set -euo pipefail

REGION=${AWS_REGION:-us-east-1}
STACK_NAME=AxonStack

echo "==> Building agent base image..."
docker build -t axon-agent-base:latest ./docker/agent-base/

echo "==> Deploying CDK infrastructure..."
cd infra
pip install -r requirements.txt -q
cdk deploy --require-approval never 2>&1 | tee /tmp/cdk-deploy.log
cd ..

# Extract outputs
INSTANCE_IP=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiPublicIp`].OutputValue' \
  --output text)

CF_DOMAIN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
  --output text)

BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
  --output text)

echo ""
echo "==> Infrastructure deployed!"
echo "    EC2 IP:     $INSTANCE_IP"
echo "    API URL:    http://$INSTANCE_IP:8000"
echo "    CF Domain:  $CF_DOMAIN"

echo ""
echo "==> Building and deploying frontend..."
cd frontend
NEXT_PUBLIC_API_URL="http://$INSTANCE_IP:8000" \
NEXT_PUBLIC_WS_URL="ws://$INSTANCE_IP:8000" \
  npm run build

# Upload static assets
aws s3 sync .next/static "s3://$BUCKET/_next/static" \
  --region "$REGION" \
  --cache-control "public,max-age=31536000,immutable"

# Upload pages (no cache — they change on deploy)
aws s3 sync out "s3://$BUCKET/" \
  --region "$REGION" \
  --cache-control "no-cache" \
  --exclude "_next/static/*" 2>/dev/null || true

cd ..

echo ""
echo "==> Deployment complete!"
echo ""
echo "    Frontend: $CF_DOMAIN"
echo "    API:      http://$INSTANCE_IP:8000"
echo ""
echo "    Next steps:"
echo "    1. SSH to EC2: ssh ubuntu@$INSTANCE_IP"
echo "    2. Copy your .env: scp .env ubuntu@$INSTANCE_IP:~/axon/"
echo "    3. Restart API: ssh ubuntu@$INSTANCE_IP 'sudo systemctl restart axon-api'"
