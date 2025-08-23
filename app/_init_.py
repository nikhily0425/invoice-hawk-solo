import os
from .ocr_extract import extract_fields
from .match_po import two_way_match
from .slack_notify import post_approval_message

def run_local(file_path: str):
    data = extract_fields(file_path)
    result = two_way_match(data)
    post_approval_message(data, result)
