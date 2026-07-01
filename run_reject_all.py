import os
from dotenv import load_dotenv

from src.triage_skill import TriageClient, triage_inbox

load_dotenv()

client = TriageClient(
    base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8099"),
    read_token=os.getenv("READ_TOKEN", "read-token-dev"),
    write_token=os.getenv("WRITE_TOKEN", "write-token-dev"),
)


def reject_all(email, action):
    print("\n--- Proposed Action Rejected ---")
    print(f"Email ID: {email.get('id')}")
    print(f"Action: {action.kind}")
    print(f"Rationale: {action.rationale}")
    return False


results = triage_inbox(client, approver=reject_all)

print("\n=== Triage Results Without Approved Writes ===")
for result in results:
    print(f"{result.email_id}: {result.label} -> {[a.kind for a in result.actions]}")