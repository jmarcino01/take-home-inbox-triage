"""Inbox Triage skill worker — STUB.

This is where you work. The signatures below are a suggested starting shape —
keep them, change them, or add to them as you see fit. Replace every
`raise NotImplementedError` with a real implementation.

You are free to choose how you classify emails (an LLM call is the obvious move —
that's the point of the role), how you structure the human-in-the-loop gate, and
how you wire the client. The requirements are in the README; how you interpret and
verify "done" is part of what we're looking at.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

import os
from dotenv import load_dotenv
load_dotenv()

# The only four labels a triage may produce.
LABELS = ("billing", "bug_report", "sales_lead", "spam")

# Which actions each classification implies. `spam` implies none.
# (Filling this in correctly is part of the task — it is intentionally empty.)
ROUTING: dict[str, list[str]] = {
    "billing": ["send_reply"],
    "bug_report": ["send_alert"],
    "sales_lead": ["send_reply", "create_lead"],
    "spam": [],
}

# Action kinds your plan may contain.
ACTION_KINDS = ("send_reply", "send_alert", "create_lead")


@dataclass
class ProposedAction:
    """An action the agent WANTS to take. Proposing is not doing — nothing here
    touches the outside world until it has been approved and executed."""

    kind: str
    payload: dict
    # Every external write requires the write scope. Reads/no-ops do not.
    requires_write: bool = True
    rationale: str = ""


@dataclass
class TriageResult:
    email_id: str
    label: str
    actions: list[ProposedAction] = field(default_factory=list)


class TriageClient:
    """Thin wrapper over the mock API. Implement the HTTP calls.

    Construct it with the base URL and the tokens it is allowed to use. Think
    about which methods need which scope.
    """

    def __init__(self, base_url: str, read_token: str, write_token: str | None = None):
        """Store configuration for the mock API client.

        base_url is the local mock API, such as http://127.0.0.1:8099.
        read_token is used for safe read-only access to /inbox.
        write_token is optional and should only be used after human approval.
        """
        self.base_url = base_url.rstrip("/")
        self.read_token = read_token
        self.write_token = write_token
        self.client = httpx.Client(timeout=30.0)

    def _headers(self, *, write: bool = False) -> dict[str, str]:
        """Create the Authorization header for read or write API calls.

        Read calls use READ_TOKEN.
        Write calls use WRITE_TOKEN and fail if no write token exists.
        This supports least privilege: read-only code does not need write access.
        """
        token = self.write_token if write else self.read_token

        if write and not token:
            raise PermissionError("Write token is required for external actions.")

        return {"Authorization": f"Bearer {token}"}

    def get_inbox(self) -> list[dict]:
        """Fetch incoming emails from the mock /inbox endpoint.

        This is a read-only operation, so it uses the read token.
        It does not require or touch the write token.
        """
        response = self.client.get(
            f"{self.base_url}/inbox",
            headers=self._headers(write=False),
        )

        response.raise_for_status()
        return response.json()

    def send_reply(self, *, to: str, subject: str, body: str, in_reply_to: str | None = None) -> dict:
        """Send a customer reply through the mock /mail/send endpoint.

        This is an external write action, so it uses the write token.
        This method should only be called by execute() after human approval.
        """
        payload = {
            "to": to,
            "subject": subject,
            "body": body,
            "in_reply_to": in_reply_to,
        }

        response = self.client.post(
            f"{self.base_url}/mail/send",
            json=payload,
            headers=self._headers(write=True),
        )

        response.raise_for_status()
        return response.json()

    def send_alert(self, *, channel: str, message: str) -> dict:
        """Send an engineering alert through the mock /slack/alert endpoint.

        This is an external write action, so it uses the write token.
        It should only be called after human approval.
        """
        payload = {
            "channel": channel,
            "message": message,
        }

        response = self.client.post(
            f"{self.base_url}/slack/alert",
            json=payload,
            headers=self._headers(write=True),
        )

        response.raise_for_status()
        return response.json()

    def create_lead(self, *, name: str, email: str, company: str | None = None, summary: str | None = None) -> dict:
        """Create a CRM lead through the mock /crm/lead endpoint.

        This is an external write action, so it uses the write token.
        It should only be called after human approval.
        """
        payload = {
            "name": name,
            "email": email,
            "company": company,
            "summary": summary,
        }

        response = self.client.post(
            f"{self.base_url}/crm/lead",
            json=payload,
            headers=self._headers(write=True),
        )

        response.raise_for_status()
        return response.json()


def classify_email(email: dict) -> str:
    """Classify an email into exactly one of the allowed labels.

    This function uses OpenAI for the classification decision, but it still
    validates the model output before trusting it. If the model returns anything
    other than one of the four allowed labels, the email is treated as spam.
    """
    from openai import OpenAI

    client = OpenAI()

    # Combine the fields that are most useful for classification. The fixtures
    # may use slightly different field names, so this safely checks several.
    email_text = "\n".join(
        str(email.get(key, ""))
        for key in ("from", "sender", "subject", "body", "text", "message")
        if email.get(key)
    )

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an email classification engine for a B2B inbox triage system. "
                    "Classify each email into exactly one of these labels: "
                    "billing, bug_report, sales_lead, spam. "
                    "Return only the label. Do not include punctuation, explanation, "
                    "markdown, quotes, or extra text."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Classify this email into exactly one allowed label.\n\n"
                    f"{email_text}"
                ),
            },
        ],
    )

    raw_label = response.choices[0].message.content or ""
    label = raw_label.strip().lower()

    # Defensive validation: never allow an unexpected model response to flow
    # into the routing table.
    if label not in LABELS:
        return "spam"

    return label

def plan_actions(label: str, email: dict) -> list[ProposedAction]:
    """Turn a classification into proposed actions.

    This function is pure and deterministic:
    - no API calls
    - no LLM calls
    - no side effects

    It only creates the action plan that a human will approve or reject later.
    """
    if label not in LABELS:
        raise ValueError(f"Invalid label: {label}")

    email_id = str(email.get("id", ""))
    sender = email.get("from") or email.get("sender") or ""
    subject = email.get("subject", "")
    body = email.get("body") or email.get("text") or email.get("message") or ""

    actions: list[ProposedAction] = []

    for kind in ROUTING[label]:
        if kind == "send_reply":
            actions.append(
                ProposedAction(
                    kind="send_reply",
                    payload={
                        "to": sender,
                        "subject": f"Re: {subject}",
                        "body": (
                            "Thanks for reaching out. We received your message "
                            "and a member of our team will follow up shortly."
                        ),
                        "in_reply_to": email_id,
                    },
                    rationale=f"{label} emails should receive a customer reply.",
                )
            )

        elif kind == "send_alert":
            actions.append(
                ProposedAction(
                    kind="send_alert",
                    payload={
                        "channel": "#engineering",
                        "message": f"Bug report from {sender}: {subject}\n\n{body}",
                    },
                    rationale="Bug reports should be routed to engineering.",
                )
            )

        elif kind == "create_lead":
            actions.append(
                ProposedAction(
                    kind="create_lead",
                    payload={
                        "name": email.get("name") or sender.split("@")[0],
                        "email": sender,
                        "company": email.get("company"),
                        "summary": f"Sales lead from inbox: {subject}",
                    },
                    rationale="Sales leads should be captured in the CRM.",
                )
            )

    return actions

def execute(action: ProposedAction, client: TriageClient, *, approved: bool) -> dict | None:
    """Execute a single proposed action, but only if a human approved it.

    This is the human-in-the-loop safety gate.

    If approved is False, this function returns immediately and does not call
    any external write endpoint. That protects against unapproved AI actions.
    """
    if not approved:
        return None

    if action.kind == "send_reply":
        return client.send_reply(**action.payload)

    if action.kind == "send_alert":
        return client.send_alert(**action.payload)

    if action.kind == "create_lead":
        return client.create_lead(**action.payload)

    raise ValueError(f"Unknown action kind: {action.kind}")


def triage_inbox(client: TriageClient, approver, classifier=classify_email) -> list[TriageResult]:
    """Run the full inbox triage workflow.

    Workflow:
    1. Fetch emails from the inbox.
    2. Classify each email.
    3. Build proposed actions from the routing table.
    4. Ask the human approver about each action.
    5. Execute only approved actions.
    6. Return one TriageResult per email for review/testing.

    The classifier is injectable so tests can use a fake classifier without
    calling a live LLM.
    """
    results: list[TriageResult] = []

    emails = client.get_inbox()

    for email in emails:
        label = classifier(email)

        if label not in LABELS:
            label = "spam"

        actions = plan_actions(label, email)

        result = TriageResult(
            email_id=str(email.get("id", "")),
            label=label,
            actions=actions,
        )

        for action in actions:
            approved = bool(approver(email, action))
            execute(action, client, approved=approved)

        results.append(result)

    return results