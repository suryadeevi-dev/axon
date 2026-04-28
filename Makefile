.PHONY: help dev build-agent infra-bootstrap infra-deploy deploy-frontend clean

help:
	@echo "AXON — development commands"
	@echo ""
	@echo "  make dev              Start full local stack (api + frontend + dynamo)"
	@echo "  make build-agent      Build the agent base Docker image"
	@echo "  make infra-bootstrap  Bootstrap CDK in your AWS account (once)"
	@echo "  make infra-deploy     Deploy CDK stack to AWS"
	@echo "  make deploy-frontend  Build + upload frontend to S3"
	@echo "  make clean            Remove all local containers/volumes"

# ── Local Development ──────────────────────────────────────────────────────
dev:
	@cp -n .env.example .env 2>/dev/null || true
	docker compose up --build

dev-bg:
	docker compose up -d --build

logs:
	docker compose logs -f

stop:
	docker compose stop

# ── Docker ─────────────────────────────────────────────────────────────────
build-agent:
	docker build -t axon-agent-base:latest ./docker/agent-base/

# ── Infrastructure ─────────────────────────────────────────────────────────
infra-bootstrap:
	cd infra && pip install -r requirements.txt && cdk bootstrap

infra-deploy: build-agent
	cd infra && cdk deploy --require-approval never

infra-diff:
	cd infra && cdk diff

infra-destroy:
	@echo "WARNING: This will destroy all AWS resources."
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	cd infra && cdk destroy --force

# ── Frontend Deployment ─────────────────────────────────────────────────────
deploy-frontend:
	@BUCKET=$$(cd infra && cdk output FrontendBucketName 2>/dev/null | tail -1); \
	if [ -z "$$BUCKET" ]; then echo "Run make infra-deploy first"; exit 1; fi; \
	cd frontend && npm run build && \
	aws s3 sync .next/static s3://$$BUCKET/_next/static --delete && \
	aws cloudfront create-invalidation --distribution-id $$(cd ../infra && cdk output CloudFrontUrl 2>/dev/null) --paths "/*" || true; \
	echo "Frontend deployed to S3: $$BUCKET"

# ── Cleanup ────────────────────────────────────────────────────────────────
clean:
	docker compose down -v --remove-orphans
	docker rmi axon-agent-base:latest 2>/dev/null || true

frontend-install:
	cd frontend && npm install

backend-install:
	cd backend && pip install -r requirements.txt
