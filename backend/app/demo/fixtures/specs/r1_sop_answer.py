"""R1 — what our phishing procedure says to do after a user clicked a reported link (RAG).

Plan: plans/2026-09-29_1536_ec-r1-rag-procedure-question.md (rev 3).

A procedure question: the knowledge base answers it, not telemetry, so there is no Splunk search.
The screen shows the procedure's steps (each citing the section it comes from), then the action
items, which are proposed together with the answer.
"""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.rag_record import (
    ProcedureStep,
    RagChunk,
    RagDocument,
    RagExclusion,
    RagFunnel,
    RagIndex,
    RagRecord,
    answer_lines,
)
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

_SOP = E.SOP_PHISHING
_SOP_VERSION = "2026.3"


def _sop_chunk(
    ref: str,
    number: int,
    section: str,
    *,
    tokens: int,
    dense_score: float,
    dense_rank: int,
    bm25_score: float,
    bm25_rank: int,
    rerank_score: float,
    excerpt: str,
    used_for: str,
    used: bool = True,
) -> RagChunk:
    """A chunk of the phishing SOP; ``number`` is its position in the chunked document."""
    return RagChunk(
        ref=ref,
        chunk_id=f"{_SOP}@{_SOP_VERSION}#c{number:02d}",
        doc_id=_SOP,
        section=f"{ref} {section}",
        tokens=tokens,
        dense_score=dense_score,
        dense_rank=dense_rank,
        bm25_score=bm25_score,
        bm25_rank=bm25_rank,
        rerank_score=rerank_score,
        excerpt=excerpt,
        used_for=used_for,
        used=used,
    )


RETRIEVAL = RagRecord(
    title="Phishing — user clicked a link",
    opening=(
        f"{E.PHISH_USER} in Finance clicked a link in a reported phishing email. Our procedure treats this as P3 "
        "until we know whether a password or other sensitive information was shared. Contain the account and the "
        f"email now, warn staff, and ask {E.PHISH_USER}."
    ),
    query="reported phishing email · user clicked link · required response steps · escalation criteria",
    collections=("SOC SOPs", "Escalation matrix", "Priority policy"),
    documents=(
        RagDocument(_SOP, "Phishing response procedure", _SOP_VERSION, "12 Mar 2026"),
        RagDocument(E.ESCALATION_MATRIX, "SOC escalation matrix", "2026.1", "20 Jan 2026"),
        RagDocument(E.PRIORITY_POLICY, "Incident priority policy", "2026.2", "4 Feb 2026"),
    ),
    index=RagIndex(
        embedding_model="BAAI/bge-m3",
        embedding_dims=1024,
        sparse_method="BM25",
        reranker_model="BAAI/bge-reranker-v2-m3",
        documents=41,
        chunks=1286,
        chunking="section-aware, 512-token max, 64-token overlap",
    ),
    funnel=RagFunnel(
        dense_candidates=40,
        sparse_candidates=40,
        fused=58,
        fusion="reciprocal rank fusion (k=60)",
        reranked=12,
        rerank_threshold=0.50,
    ),
    exclusions=(
        RagExclusion("superseded", 3, _SOP, "2025.4", f"{_SOP} v2025.4, replaced by v{_SOP_VERSION}"),
        RagExclusion("draft", 1, "SOC-SOP-PHISH-002", "0.4", "SOC-SOP-PHISH-002 Invoice fraud v0.4, not approved"),
        RagExclusion("expired", 1, "SOC-AWR-BUL-2411", "2024.11", "Phishing awareness bulletin 2024-11, past review date"),
    ),
    chunks=(
        _sop_chunk(
            "3.2", 7, "Contain the account", tokens=212,
            dense_score=0.861, dense_rank=1, bm25_score=15.4, bm25_rank=1, rerank_score=0.96,
            excerpt=(
                "If the user clicked a link, reset the user's password and revoke active sessions within 4 hours, "
                "whether or not credential entry is confirmed."
            ),
            used_for="Reset password and sign out sessions",
        ),
        _sop_chunk(
            "3.3", 8, "Contain the message", tokens=198,
            dense_score=0.824, dense_rank=2, bm25_score=11.7, bm25_rank=3, rerank_score=0.94,
            excerpt=(
                "Remove the message from all mailboxes by message ID and block the sender address at the email "
                "gateway. Record the purge count in the incident."
            ),
            used_for="Remove the email and block the sender",
        ),
        _sop_chunk(
            "3.1", 6, "Open an incident", tokens=188,
            dense_score=0.812, dense_rank=3, bm25_score=12.9, bm25_rank=2, rerank_score=0.92,
            excerpt=(
                "For every reported phishing message a user interacted with, open an incident. Set priority per "
                f"{E.PRIORITY_POLICY}; do not raise it on the report alone."
            ),
            used_for="Open an incident",
        ),
        _sop_chunk(
            "3.6", 11, "Warn staff", tokens=167,
            dense_score=0.806, dense_rank=4, bm25_score=11.1, bm25_rank=4, rerank_score=0.90,
            excerpt=(
                "Ask Internal Communications to send a staff advisory the same day with the sender, subject and a "
                "defanged link. Tell staff not to click and to report any copy they received."
            ),
            used_for="Staff advisory",
        ),
        _sop_chunk(
            "3.4", 9, "Notify the user", tokens=174,
            dense_score=0.797, dense_rank=5, bm25_score=10.2, bm25_rank=6, rerank_score=0.88,
            excerpt=(
                "Tell the user what was done and ask whether they entered credentials, shared sensitive "
                "information, approved an MFA prompt or opened an attachment. Record the answer."
            ),
            used_for="Tell the user and ask what they shared",
        ),
        RagChunk(
            ref="PH-02",
            chunk_id=f"{E.ESCALATION_MATRIX}@2026.1#c14",
            doc_id=E.ESCALATION_MATRIX,
            section="PH-02 Phishing — user interaction",
            tokens=96,
            dense_score=0.774, dense_rank=7, bm25_score=10.8, bm25_rank=5, rerank_score=0.86,
            excerpt=(
                "Owner: SOC Tier 1. Escalate to Tier 2 on credential entry, sensitive data shared, MFA approval, "
                "or more than 10 recipients clicking."
            ),
            used_for="Escalation rule",
        ),
        _sop_chunk(
            "4.1", 12, "Scope the recipients", tokens=183,
            dense_score=0.781, dense_rank=6, bm25_score=9.9, bm25_rank=7, rerank_score=0.83,
            excerpt=(
                "Search the email gateway logs for every recipient of the message, and proxy logs for everyone "
                "who opened the link."
            ),
            used_for="Find who else received or opened it",
        ),
        _sop_chunk(
            "4.2", 13, "Check the endpoint", tokens=152,
            dense_score=0.752, dense_rank=9, bm25_score=8.7, bm25_rank=9, rerank_score=0.80,
            excerpt="Check endpoint telemetry for processes started by the browser in the 30 minutes after the click.",
            used_for="Check the laptop after the click",
        ),
        _sop_chunk(
            "3.5", 10, "Isolate the endpoint", tokens=141,
            dense_score=0.745, dense_rank=10, bm25_score=8.9, bm25_rank=8, rerank_score=0.77,
            excerpt=(
                "Isolate the endpoint only if a file was downloaded or executed after the click. Do not power it "
                "off."
            ),
            used_for="Conditional isolation",
        ),
        RagChunk(
            ref="Rule 3",
            chunk_id=f"{E.PRIORITY_POLICY}@2026.2#c03",
            doc_id=E.PRIORITY_POLICY,
            section="Rule 3",
            tokens=81,
            dense_score=0.702, dense_rank=12, bm25_score=6.1, bm25_rank=13, rerank_score=0.71,
            excerpt="Attempted misuse with no access gained, on a non-critical asset: P3.",
            used_for="Priority P3",
        ),
        _sop_chunk(
            "5.1", 14, "Credential entry confirmed", tokens=205,
            dense_score=0.768, dense_rank=8, bm25_score=9.4, bm25_rank=10, rerank_score=0.64,
            excerpt=(
                "If the user entered credentials or shared sensitive data, treat it as account compromise: escalate "
                f"to Tier 2 and follow {E.SOP_PRIV_LOGON}."
            ),
            used_for="Not applied — nothing shared is confirmed yet",
            used=False,
        ),
    ),
    steps=(
        ProcedureStep(
            "Contain", "Reset the password and sign out all sessions within 4 hours", "IAM", ("3.2",),
            action_id="reset_credentials", short="password reset",
        ),
        ProcedureStep(
            "Contain", "Remove the email from all mailboxes and block the sender", "Email team", ("3.3",),
            action_id="purge_and_block", short="email removal and sender block",
        ),
        ProcedureStep(
            "Contain", "Isolate the laptop", "Endpoint team", ("3.5",),
            condition="only if a file was downloaded or ran", short="laptop isolation",
        ),
        ProcedureStep(
            "Scope", "Find everyone who received or opened the email", "SOC", ("4.1",),
            short="find other recipients",
        ),
        ProcedureStep(
            "Scope", "Check the laptop for anything that ran after the click", "SOC", ("4.2",),
            short="check the laptop",
        ),
        ProcedureStep(
            "Record and notify", "Open an incident at policy priority — P3 for a click", "SOC Tier 1", ("3.1", "Rule 3"),
            action_id="open_incident", short="incident",
        ),
        ProcedureStep(
            "Record and notify", "Warn staff with an advisory: sender, subject, do not click", "Internal Comms", ("3.6",),
            action_id="issue_advisory", short="staff advisory",
        ),
        ProcedureStep(
            "Record and notify", "Tell the user; ask if they entered a password or shared sensitive information",
            "SOC Tier 1", ("3.4",), action_id="email_user", short="ask the user",
        ),
    ),
    escalation=ProcedureStep(
        "Escalate",
        "Escalate to Tier 2 if a password or sensitive information was shared, an MFA prompt was approved, or more "
        "than 10 people clicked",
        "SOC Tier 1",
        ("PH-02",),
    ),
    gaps=(f"How long to keep the sender blocked — {_SOP} sets no review date.",),
    governance=(
        "Hybrid retrieval: dense BAAI/bge-m3 embeddings and BM25, fused by reciprocal rank, reranked by "
        "BAAI/bge-reranker-v2-m3.",
        f"Only approved, current versions are searchable; 5 chunks were excluded before reranking, including "
        f"{_SOP} v2025.4, replaced by v{_SOP_VERSION}.",
        "Every step cites the section it rests on; a kept chunk that does not apply is shown, not cited.",
        "Retrieved text is evidence for the answer, not instructions to the system.",
    ),
)

R1 = ScenarioSpec(
    scenario_id="r1_rag_privileged_success_after_failure",
    family="r1_governed_rag",
    label="R1 · What does our phishing procedure say? (knowledge base)",
    question=(
        f"{E.PHISH_USER} from Finance reported a phishing email and says they clicked the link. What does our "
        "phishing procedure say we should do?"
    ),
    demo_order=8,
    plan_title="Phishing procedure — plan ready",
    plan_intro=(
        "I'll look up our phishing procedure and the escalation matrix in the knowledge base, then propose the "
        "actions it calls for. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="sop",
            title="What does our phishing procedure say?",
            plan=f"Retrieve the steps for a clicked phishing link from {_SOP}.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {_SOP}",
            result=f"{_SOP} v{_SOP_VERSION} (approved 12 Mar 2026): 8 steps apply to a click; top match 3.2, rerank 0.96.",
            evidence=(f"{_SOP} v{_SOP_VERSION}; superseded v2025.4 excluded before reranking",),
        ),
        Check(
            id="escalation",
            title="When do we escalate?",
            plan=f"Retrieve the phishing row of {E.ESCALATION_MATRIX}.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.ESCALATION_MATRIX}",
            result="PH-02: Tier 1 owns it; Tier 2 only if a password or sensitive data was shared, an MFA prompt approved, or more than 10 clicked.",
            evidence=(f"{E.ESCALATION_MATRIX} v2026.1, row PH-02",),
        ),
    ),
    # Shown large as the answer's headline; the opening sits under it in the procedure card.
    conclusion_headline="Phishing procedure found — 5 actions ready for approval",
    points=answer_lines(RETRIEVAL),
    rag=RETRIEVAL,
    propose_with_answer=True,
    unresolved=(f"Did {E.PHISH_USER} enter a password or share sensitive information? This decides escalation.",),
    not_proposed=("No Tier 2 escalation yet — none of the PH-02 conditions is met",),
    threat="Suspected",
    asset_tier=2,
    evidence_state="attempted_misuse",
    subject=f"Reported phishing — {E.PHISH_USER}",
    decision=(
        f"Proposed, as {_SOP} requires: open a {{priority}} incident, reset {E.PHISH_USER}'s password, remove the "
        "email and block the sender, ask for a staff advisory, and tell the user."
    ),
    actions=(
        Action(
            id="open_incident",
            title="Open a {priority} incident",
            proposal=f"ITSM incident at {{priority}} ({{priority_basis}}), with the cited procedure attached ({_SOP} 3.1).",
            tool="itsm",
            verb="incident",
            ticket_id=E.INCIDENT_R1,
            ticket_summary=f"Reported phishing — {E.PHISH_USER} clicked the link",
            assignment_group="SOC Tier 1",
            executed=f"Incident {E.INCIDENT_R1} opened ({{priority}})",
        ),
        Action(
            id="reset_credentials",
            title="Reset the password and sign out sessions",
            proposal=f"Request to IAM: reset {E.PHISH_USER}'s password and revoke sessions within 4 hours ({_SOP} 3.2).",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_R1_IAM,
            ticket_summary=f"Reset {E.PHISH_USER} password and revoke sessions",
            assignment_group="Identity & Access Management",
            executed=f"Request {E.TASK_R1_IAM} raised with IAM",
            status_after="REQUESTED",
        ),
        Action(
            id="purge_and_block",
            title="Remove the email and block the sender",
            proposal=f"Request to the email team: purge the message from all mailboxes, block {E.PHISH_SENDER} ({_SOP} 3.3).",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_R1_MAIL,
            ticket_summary=f"Purge reported phishing message and block {E.PHISH_SENDER}",
            assignment_group="Messaging & Email Security",
            executed=f"Request {E.TASK_R1_MAIL} raised with the email team",
            status_after="REQUESTED",
        ),
        Action(
            id="issue_advisory",
            title="Ask Internal Communications to send a staff advisory",
            proposal=(
                f"Request to Internal Communications with the advisory text: sender, subject, defanged link, do not "
                f"click ({_SOP} 3.6)."
            ),
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_R1_COMMS,
            ticket_summary=f'Staff phishing advisory — "{E.PHISH_SUBJECT}"',
            assignment_group="Internal Communications",
            ticket_description=(
                "Please send this advisory to all staff today.\n\n"
                "A phishing email is being sent to our staff. Do not click the link in it.\n"
                f"From: {E.PHISH_SENDER}\n"
                f"Subject: {E.PHISH_SUBJECT}\n"
                f"Link: {E.PHISH_URL}\n"
                "If you received it: do not click the link. Report it with the Report Phish button, then delete it.\n"
                "If you clicked the link, entered your password or shared any information: contact the SOC through "
                "the service desk now.\n\n"
                "SOC reference: {ticket:open_incident}"
            ),
            executed=f"Request {E.TASK_R1_COMMS} raised with Internal Communications",
            status_after="REQUESTED",
        ),
        Action(
            id="email_user",
            title=f"Email {E.PHISH_USER}: what we did, and what they shared",
            proposal=(
                f"Short email to {E.PHISH_USER} with the incident reference: did they enter a password or share "
                f"sensitive information ({_SOP} 3.4)."
            ),
            tool="email",
            verb="email",
            email=Email(
                to=E.PHISH_USER,
                mailbox="INCIDENT_OWNER",
                subject="[{ticket:open_incident}] The email you reported — what happens next",
                body=(
                    "Reference: {ticket:open_incident}\n\n"
                    "Thanks for reporting the suspicious email. We are resetting your password and signing out "
                    "your active sessions, and removing the email from every mailbox.\n\n"
                    "Please reply today: after clicking, did you enter your password, share any sensitive "
                    "information (for example bank or card details), approve a sign-in prompt, or open an "
                    "attachment? Either answer is fine — it tells us whether to escalate.\n\n"
                    "{tickets}\n\n"
                    "SOC Tier 1"
                ),
            ),
            executed=f"Sent to {E.PHISH_USER}",
            status_after="AWAITING_REPLY",
        ),
    ),
    final_state="OPEN — AWAITING USER REPLY",
    final_headline="Incident open, containment and advisory requested — awaiting the user's reply",
    pending=(f"{E.PHISH_USER}'s reply: password or sensitive information shared?",),
    next_triggers=(
        f"If a password or sensitive information was shared, or a prompt approved, escalate to Tier 2 "
        f"({E.ESCALATION_MATRIX} PH-02)."
    ),
)
