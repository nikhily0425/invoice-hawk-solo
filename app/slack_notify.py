import os, json, requests
def post_approval_message(payload: dict, match: dict):
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url: 
        print("[warn] SLACK_WEBHOOK_URL not set; skipping Slack")
        return
    text = f"Invoice {payload['invoice_no']} from {payload['vendor']} • Match: {match['matched']}"
    requests.post(url, json={"text": text})
