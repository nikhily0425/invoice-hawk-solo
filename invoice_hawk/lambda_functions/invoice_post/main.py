import json
import base64
import logging
from invoice_hawk.utils import get_db_session
from invoice_hawk.models import Invoice, AuditLog
from invoice_hawk.netsuite_client import NetSuiteClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler to post an invoice to NetSuite.
    Expects JSON body with {"invoice_id": <id>}.
    Returns {"posted": true, "external_id": "..."} in success case.
    """

    try:
        # --- Parse body ---
        body = event.get("body")
        if not body:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing request body"})
            }

        # Decode if necessary
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode()

        data = json.loads(body)

        invoice_id = data.get("invoice_id")
        if not invoice_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing invoice_id"})
            }

        logger.info("Invoice post request for ID %s", invoice_id)

        # --- DB Lookup ---
        with get_db_session() as session:
            invoice = session.get(Invoice, invoice_id)
            if not invoice:
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": "Invoice not found"})
                }

            # --- Call NetSuite test-mode posting ---
            client = NetSuiteClient()
            result = client.post_invoice(invoice)
            external_id = result.get("external_id")

            if external_id:
                invoice.external_id = external_id
                invoice.status = "posted"

                session.add(
                    AuditLog(
                        event_type="post_to_netsuite",
                        details={"external_id": external_id},
                        invoice=invoice
                    )
                )
                session.commit()

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "posted": True,
                        "external_id": external_id
                    })
                }

            # No external_id returned (should never happen in test mode)
            return {
                "statusCode": 502,
                "body": json.dumps({"error": "Failed to post invoice"})
            }

    except Exception as e:
        logger.exception("Error in invoice_post handler: %s", e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }