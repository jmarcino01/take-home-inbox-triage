# Engineering Manager's Log

> One page. This is where you show us how you *directed* the AI — it matters as much
> as the code. Be concrete. Bullet points are fine.

**Name:** Joshua Marcinowski
**Time spent (be honest):** About 1.5 HRS

---

## How I broke the work down
I broke the work into the smallest pieces that would prove the core requirements before adding polish:

First, I got the local environment running: virtual environment, dependencies, .env, and the mock API server.
Then I inspected the README, env.example, and src/triage_skill.py to understand the expected workflow and where implementation belonged.
I implemented the API client first because the rest of the skill depends on being able to read /inbox and call the mock write endpoints.
Next, I filled in the routing table and plan_actions() as a pure function. I wanted classification and planning to be separated from external side effects.
Then I implemented the OpenAI-based classifier with strict output validation so the model could only route one of the four allowed labels: billing, bug_report, sales_lead, or spam.
After that, I implemented execute() as the human-in-the-loop gate. This was the most important safety boundary: if approved is false, the function returns immediately and does not call any write endpoint.
Finally, I added demo scripts to prove both the approved path and rejected path using the mock API audit endpoint.

## Where I ran things in parallel
I used multiple terminals and windows:

One terminal kept the mock API server running with uvicorn on 127.0.0.1:8099.
A second terminal was used for running python run.py, python run_reject_all.py, py_compile, and audit checks.
VS Code stayed open for editing the implementation, README, and engineering log.
ChatGPT was used as a coding partner to help decompose the problem, review implementation order, and check the safety implications of each step.

I kept the work organized by testing after each meaningful change. For example, after implementing the client and functions, I ran:

python -m py_compile src/triage_skill.py

Then I used:

curl -s http://127.0.0.1:8099/_audit | python -m json.tool

to confirm whether external side effects had or had not occurred.

## One time the AI was wrong, and how I caught it
One AI-generated edit accidentally duplicated the __init__ function inside the TriageClient constructor. That would have broken the module before any real testing could happen.

I caught it by reviewing the code manually and then running:

python -m py_compile src/triage_skill.py

I fixed the constructor so it only stored the base URL, read token, write token, and reusable httpx.Client. This was a useful reminder not to blindly trust generated patches, especially under time pressure. I treated the AI output as a draft and verified each step with syntax checks and runtime tests.

## What I deliberately cut to fit the 2 hours
I deliberately kept the project focused on the core workflow instead of overbuilding.

I did not build:

A web UI for approvals.
Persistent storage for triage history.
Fully customized reply drafting per customer.
A large pytest suite.
Complex CRM enrichment or company-name extraction.
Retry/backoff logic for production API failures.

The tradeoff I accepted was that the demo scripts are simple, but they clearly prove the most important requirements: classification, routing, human approval, least-privilege separation, approved writes, and rejected/no-write behavior.

Given more time, I would add unit tests around plan_actions(), execute(), and triage_inbox() using fake classifiers and fake approvers.

## The design decision I'm proudest of
The design decision I am proudest of is separating proposed actions from executed actions.

plan_actions() is pure and deterministic. It creates ProposedAction objects but does not call the network, send mail, alert engineering, or create CRM leads. That means the AI classifier and planner can suggest what should happen without being able to mutate external systems.

execute() is the only place where write actions happen, and it immediately returns None if approved is false. I verified this by running a reject-all demo and checking that the audit log stayed empty:

{
    "sent_mail": [],
    "alerts": [],
    "leads": []
}

I also kept read and write credentials separate in TriageClient. Reading the inbox uses the read token, while mail, Slack alerts, and CRM lead creation require the write token. This supports least privilege and makes the spam path safer because spam produces no proposed write actions at all.
