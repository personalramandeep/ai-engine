#!/bin/bash
# Run this ONCE before the first `terraform apply`
# Usage: bash infra/bootstrap.sh <s3_bucket_name> <webhook_url> <hmac_secret>

set -e

REGION="ap-south-1"
TFSTATE_BUCKET="kreeda-ai-engine-tfstate"

echo "=== Creating Terraform state bucket ==="
aws s3api create-bucket \
  --bucket $TFSTATE_BUCKET \
  --region $REGION \
  --create-bucket-configuration LocationConstraint=$REGION

aws s3api put-bucket-versioning \
  --bucket $TFSTATE_BUCKET \
  --versioning-configuration Status=Enabled

echo "=== Storing secrets in SSM Parameter Store ==="
aws ssm put-parameter --region $REGION --name "/kreeda/S3_BUCKET"        --value "$1" --type SecureString --overwrite
aws ssm put-parameter --region $REGION --name "/kreeda/WEBHOOK_BASE_URL" --value "$2" --type SecureString --overwrite
aws ssm put-parameter --region $REGION --name "/kreeda/HMAC_SECRET"      --value "$3" --type SecureString --overwrite

echo "=== Done. Now run: cd infra && terraform init && terraform apply ==="
