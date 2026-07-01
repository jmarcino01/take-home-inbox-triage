import os
from dotenv import load_dotenv

from src.triage_skill import TriageClient, triage_inbox

load_dotenv()

client = TriageClient(
    base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8099"),
    read_token=os.getenv("READ_TOKEN", "read-token-dev"),
    write_token=os.getenv("WRITE_TOKEN", "write-token-dev"),
)


def approve_all(email, action):
    print("\n--- Proposed Action ---")
    print(f"Email ID: {email.get('id')}")
    print(f"Action: {action.kind}")
    print(f"Rationale: {action.rationale}")
    print(f"Payload: {action.payload}")
    return True


results = triage_inbox(client, approver=approve_all)

print("\n=== Triage Results ===")
for result in results:
    print(f"{result.email_id}: {result.label} -> {[a.kind for a in result.actions]}")