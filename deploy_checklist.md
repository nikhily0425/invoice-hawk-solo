# Invoice Hawk Week 4 Deployment Checklist

This document provides a step‑by‑step guide to deploying the Invoice Hawk
MVP to a staging environment on AWS using the Serverless Framework.  It
also describes how to perform a basic smoke test and how to roll back
the deployment if necessary.

## Prerequisites

1. **AWS Account and Credentials** – You need an AWS account with
   permissions to create Lambda functions, API Gateway endpoints,
   S3 buckets, and IAM roles.  Configure credentials via the AWS CLI
   (`aws configure`) or set `AWS_ACCESS_KEY_ID` and
   `AWS_SECRET_ACCESS_KEY` environment variables.  The deployment
   defaults to the `us‑east‑1` region; override using `AWS_REGION` if
   needed.
2. **Serverless Framework** – Install the Serverless CLI globally:
   ```bash
   npm install -g serverless
   ```
3. **Slack Workspace** – Create a Slack app or incoming webhook and
   obtain the **Slack signing secret** (`SLACK_SIGNING_SECRET`) and
   **webhook URL** (`SLACK_WEBHOOK_URL`).  Configure the interactive
   endpoint to point to `/slack/actions` after deployment.
4. **Optional** – An OpenAI API key (`OPENAI_API_KEY`) for GPT Vision
   OCR; if omitted, the system falls back to a stub provider.
5. **Optional** – NetSuite sandbox credentials (`NETSUITE_*`); the
   default test mode avoids any external calls.

## Deployment Steps

1. **Clone and prepare the repository**

   ```bash
   git clone https://github.com/nikhily0425/invoice-hawk-solo.git
   cd invoice-hawk-solo
   git checkout invoice-hawk/dev4
   ```

2. **Create a `.env` file** (optional) or export environment variables.

   Minimum required variables:
   ```env
   DATABASE_URL=sqlite:///tmp.db    # or postgres://user:pass@host/db
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/…
   SLACK_SIGNING_SECRET=your-slack-signing-secret
   # Optional: provide ARCHIVE_BUCKET to use an existing bucket
   # Optional: OPENAI_API_KEY, NETSUITE_BASE_URL, NETSUITE_TOKEN, etc.
   NETSUITE_TEST_MODE=true         # default; keeps calls stubbed
   ```

   If `ARCHIVE_BUCKET` is not set, Serverless will create a bucket
   named `invoice-hawk-<stage>-archive`.

3. **Install Python dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run tests** (optional but recommended).  Ensure coverage remains
   above 70 %:

   ```bash
   pytest --cov=invoice_hawk --cov-report=term
   ```

5. **Deploy to AWS**

   ```bash
   # Ensure AWS credentials are exported (see prerequisites)
   serverless deploy --stage dev
   ```

   The deploy command will package the functions, create the
   required IAM roles and S3 bucket (if needed), and output the API
   endpoints.  Make a note of the `/ocr` and `/slack/actions` URLs.

6. **Configure Slack**

   In your Slack app configuration, set the interactivity request URL
   to the `/slack/actions` endpoint printed by the deployment.  Ensure
   the signing secret matches `SLACK_SIGNING_SECRET` in your environment.

7. **Run smoke tests**

   Use the provided script to verify the endpoints:

   ```bash
   export OCR_URL=<ocr-endpoint-from-deploy>
   export SLACK_URL=<slack-actions-endpoint-from-deploy>
   export SLACK_SECRET=<your-slack-signing-secret>
   ./scripts/smoke.sh
   ```

   The script will send a tiny PDF to the OCR endpoint and a signed
   payload to the Slack actions endpoint.  Both should return
   successful responses.

## Rollback / Removal

To remove the deployed stack and all associated resources:

```bash
serverless remove --stage dev
```

This command deletes the Lambda functions, API Gateway, S3 bucket, and
IAM roles created during deployment.  Use it to roll back changes if
something goes wrong or to avoid incurring ongoing costs.

## Smoke Test Notes

- The OCR test uses a base64‑encoded blank PDF.  In production, the
  Lambda will extract fields from real invoices and perform a two‑way
  match against a purchase order.  When `OPENAI_API_KEY` is not set,
  the fallback provider returns deterministic stub data.
- The Slack actions test signs the payload using your Slack signing
  secret.  The endpoint simply acknowledges the request and updates
  the invoice status; interactive button flows are not yet fully
  wired in Week 4.

## Cost Considerations

This MVP is designed to minimise AWS costs:

- **Lambda** – Functions are invoked on demand and limited to a single
  concurrent execution by default.
- **S3** – Archiving uses an S3 bucket that can be configured or
  created automatically.  Storage costs scale with the number of PDFs
  and extracted JSON files.
- **API Gateway** – Costs accrue per invocation of the `/ocr` and
  `/slack/actions` endpoints.  Using HTTP API (not REST API) keeps
  these costs lower.
- **NetSuite** – The client operates in test mode by default, avoiding
  any charges or API rate limits.