"""
Lambda handler to ingest invoice emails from an IMAP mailbox and store PDF
attachments in S3.

This function is designed to run on a schedule (e.g. via EventBridge) and
connects to an IMAP server using credentials supplied via environment
variables.  It iterates through unread emails, extracts PDF attachments, and
uploads them to the configured S3 bucket.
"""

import email
import imaplib
import os
from email.message import EmailMessage
from typing import List, Tuple

from invoice_hawk.utils import upload_file_to_s3


def _connect_imap() -> imaplib.IMAP4_SSL:
    host = os.environ.get("IMAP_HOST")
    port = int(os.environ.get("IMAP_PORT", "993"))
    user = os.environ.get("IMAP_USERNAME")
    password = os.environ.get("IMAP_PASSWORD")
    if not all([host, user, password]):
        raise RuntimeError("Missing IMAP configuration")
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(user, password)
    return mail


def _fetch_unread_emails(mail: imaplib.IMAP4_SSL) -> List[Tuple[bytes, bytes]]:
    mail.select("INBOX")
    status, data = mail.search(None, "UNSEEN")
    if status != "OK":
        return []
    messages = []
    for num in data[0].split():
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status == "OK":
            messages.extend(msg_data)
        # mark as seen
        mail.store(num, "+FLAGS", "\\Seen")
    return messages


def _extract_pdf_attachments(msg: EmailMessage) -> List[Tuple[str, bytes]]:
    attachments = []
    for part in msg.walk():
        content_disposition = part.get("Content-Disposition", "")
        if part.get_content_type() == "application/pdf" and "attachment" in content_disposition:
            filename = part.get_filename() or "attachment.pdf"
            attachments.append((filename, part.get_payload(decode=True)))
    return attachments


def handler(event, context):  # pragma: no cover - entry point called by AWS
    bucket = os.environ.get("INVOICE_BUCKET")
    if not bucket:
        raise RuntimeError("Missing INVOICE_BUCKET environment variable")
    mail = _connect_imap()
    raw_messages = _fetch_unread_emails(mail)
    for _, raw in raw_messages:
        msg = email.message_from_bytes(raw)
        attachments = _extract_pdf_attachments(msg)
        for filename, content in attachments:
            key = os.path.join("inbox", filename)
            upload_file_to_s3(content, bucket, key)
    return {"status": "success", "processed": len(raw_messages)}