# Security Policy

## Least-Privilege IAM

Invoice Hawk uses AWS IAM roles with least-privilege permissions. Each Lambda function is granted only the permissions needed: S3 `PutObject`/`ListBucket` access to the archive bucket and CloudWatch Logs permissions. The Serverless configuration defines these statements under `provider.iam.role.statements`. If additional permissions are required (for example Secrets Manager access), scope them to specific resources.

## API Gateway Safety

The HTTP API endpoints for OCR extraction, Slack actions, and invoice posting are protected by verifying request signatures (for Slack) and by accepting only JSON or form-encoded payloads. The Slack actions endpoint validates both the timestamp and signature using the Slack signing secret to prevent replay attacks. When deploying publicly accessible endpoints, configure AWS API Gateway to enforce HTTPS, limit allowed methods, and enable throttling to mitigate abuse.

## Environment Variables

Sensitive credentials such as database URLs, Slack tokens, NetSuite tokens, and OpenAI keys are injected via environment variables and are not committed to source control. In production, these should be stored securely in AWS Secrets Manager or Parameter Store and referenced in the Serverless configuration.

## Cost and Tagging

All AWS resources are tagged with `project=invoice-hawk` and `env=staging` to facilitate cost allocation and monitoring. S3 bucket names are stage-scoped to avoid accidental data overlap across environments.

## Test Mode

By default, NetSuite integration runs in a test mode (`NETSUITE_TEST_MODE=true`) to avoid real financial postings. This mode should be disabled only after thorough testing and when valid credentials are provided.
