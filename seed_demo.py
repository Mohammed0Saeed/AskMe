"""
SIX Group Demo Data Seed — run once: python seed_demo.py
Content reflects real operational cases SIX Group employees handle:
  • SIC / euroSIC payment infrastructure
  • Securities settlement (SIX SIS / SECOM)
  • Corporate actions processing
  • MiFIR / FINMA regulatory reporting
  • Incident & change management
  • Participant onboarding
  • Reference data (ISIN / VALOR)
  • Market surveillance
"""
import json, os, sys, uuid
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from generation import provider_config as _pc; _pc.load()
from ingestion  import IngestionPipeline
from retrieval  import RetrievalPipeline

ingest    = IngestionPipeline()
retrieval = RetrievalPipeline()
retrieval.load_index()

def uid12(): return uuid.uuid4().hex[:12]
NOW = datetime.now(timezone.utc)
def ts(days_ago=0, hours_ago=0):
    return (NOW - timedelta(days=days_ago, hours=hours_ago)).isoformat()
def today_minus(d):
    return (date.today() - timedelta(days=d)).isoformat()

# ─────────────────────────────────────────────────────────────────────────────
# 1.  KNOWLEDGE BASE — SIX Group operational content
# ─────────────────────────────────────────────────────────────────────────────
print("Seeding knowledge base…")

KB = [

    # ── SIC / euroSIC — Payment Infrastructure ───────────────────────────────
    dict(domain="Operations", access="internal",
         title="SIC Intraday Liquidity Management",
         text="""
SIC (Swiss Interbank Clearing) is the Swiss real-time gross settlement (RTGS) system
operated by SIX Interbank Clearing Ltd on behalf of the Swiss National Bank (SNB).

Intraday Liquidity:
Participants fund their SIC account (Giro account at the SNB) at the start of each
business day. Payments are settled individually and in real time on a gross basis —
no netting occurs. A participant must have sufficient liquidity before a payment is
released.

Queuing and Priority:
Payments that cannot settle immediately are queued in FIFO order by priority class:
  Priority 1 — SNB monetary policy transactions
  Priority 2 — Net settlement system feeds (e.g. SIX SIS, card schemes)
  Priority 3 — Interbank large-value payments
  Priority 4 — Customer payments and retail batches

Participants can reassign queue positions manually via the SIC Participant Interface.
Optimisation runs execute every 30 minutes to resolve circular gridlocks.

End-of-Day Procedure:
Cut-off for customer payments: 16:15 CET.
Cut-off for interbank payments: 17:30 CET.
Final settlement and SNB account reconciliation: 18:00 CET.
Unprocessed payments remaining after cut-off are returned to the sending participant.

Collateral and Lombard Limits:
Participants may pledge SNB-eligible collateral to obtain intraday credit (Lombard).
Collateral must be pre-positioned in the SNB collateral management system.
Lombard credit is automatically repaid from incoming payments during the day.
"""),

    dict(domain="Operations", access="internal",
         title="euroSIC Payment Processing and Cut-Off Times",
         text="""
euroSIC is SIX's cross-border RTGS system for euro-denominated payments,
connecting Swiss banks to the European payment ecosystem via TARGET2 bridging.

Supported Message Types:
  SWIFT MT103  — Single customer credit transfer
  SWIFT MT202  — General financial institution transfer
  ISO 20022 pacs.008 — Customer credit transfer (CBPR+ migration)
  ISO 20022 pacs.009 — Financial institution credit transfer

Settlement:
All euroSIC payments settle in real time against the participant's euro account
held with SIX. Participants pre-fund their accounts via TARGET2 nostro transfers.
Minimum opening balance: EUR 1,000,000 for active participants.

Cut-Off Times (CET):
  08:00 — System opens; participants may submit payments
  16:00 — Cut-off for customer payments (MT103 / pacs.008)
  17:00 — Cut-off for bank-to-bank payments (MT202 / pacs.009)
  17:30 — End-of-day settlement; remaining liquidity returned

Incident Escalation:
Payment processing failures must be reported to SIX Operations within 15 minutes.
Critical incidents (> EUR 50M impacted) are escalated to the euroSIC Incident Manager
and the Head of Payment Services immediately.

SEPA Reachability:
euroSIC participants are reachable for SEPA Credit Transfers and SEPA Instant Credit
Transfers via the SIX–EBA Clearing bridge. Maximum SEPA instant amount: EUR 100,000.
"""),

    # ── Securities Settlement — SIX SIS / SECOM ──────────────────────────────
    dict(domain="Operations", access="internal",
         title="Failed Trade Management and Buy-In Procedure (CSDR)",
         text="""
Under the EU Central Securities Depositories Regulation (CSDR) and the SIX SIS
rules, settlement fails must be monitored, reported, and resolved within defined timelines.

Settlement Cycle:
Equities and corporate bonds settle on T+2 (trade date plus 2 business days).
Government bonds and money market instruments settle on T+1 or T+0.

Failed Trade Definition:
A trade is "failed" if settlement has not occurred by the intended settlement date (ISD).
Partial settlement is permitted; the unsettled portion is re-attempted each subsequent day.

Fail Monitoring Responsibilities (Operations team):
  Day ISD+0: Auto-retry at each SECOM settlement batch (07:00, 10:00, 13:00, 15:30).
  Day ISD+1: Operations sends fail notification to both counterparties via SWIFT MT548.
  Day ISD+4: Cash penalty accrual begins (equities: 1 bp/day; bonds: 0.5 bp/day of face value).

Buy-In Process:
  Day ISD+4 (equities) or ISD+7 (bonds): receiving participant may initiate buy-in.
  Buy-in agent appointed within 2 business days.
  Buy-in execution within 4 business days.
  If buy-in unsuccessful, the trade is cash-compensated at last available market price.
  SIX SIS charges a buy-in administration fee of CHF 500 per transaction.

Reporting:
All fail data is reported to FINMA monthly via the CSDR fail rate report.
Participants with a fail rate exceeding 1% receive a formal notification from SIX SIS.
"""),

    dict(domain="Operations", access="internal",
         title="Corporate Actions Processing at SIX SIS",
         text="""
SIX SIS processes corporate actions on behalf of issuing agents and notifies
participants holding the affected securities in their custody accounts.

Event Types Supported:
  Mandatory: Cash dividend, stock dividend, capital repayment, redemption,
             stock split, reverse split, merger, delisting
  Voluntary: Rights issue subscription, tender offer, exchange offer,
             consent solicitation, optional dividend (cash or stock)

Processing Timeline (standard mandatory event):
  T-10: SIX SIS publishes event announcement in SECOM (SWIFT MT564)
  T-3:  Record date confirmed; positions frozen for entitlement calculation
  T-0:  Record date — entitlement snapshot taken at end-of-day
  T+1:  Entitlements calculated and credited to participant accounts
  T+2 (or pay date): Cash proceeds or new securities delivered

Key Participant Obligations:
  Participants must respond to voluntary events by the election deadline (typically T-3
  before payment date). Late elections are not accepted.
  For rights issues, unexercised rights are sold in the market and the net proceeds
  credited to the participant (rump auction).

Errors and Disputes:
  Entitlement discrepancies must be reported to SIX SIS Corporate Actions within
  3 business days of the credit/debit notification.
  Retrospective adjustments are only possible within 20 business days of the event.
  Late claims are rejected; the cost falls on the participant who failed to report in time.
"""),

    # ── Reference Data — ISIN / VALOR ────────────────────────────────────────
    dict(domain="Technology", access="internal",
         title="ISIN and VALOR Number Assignment — Reference Data Services",
         text="""
SIX Financial Information acts as the Swiss National Numbering Agency (NNA) and
is responsible for assigning ISIN codes and VALOR numbers to Swiss-domiciled securities.

ISIN (International Securities Identification Number):
Structure: 2-letter country code + 9-character alphanumeric NSIN + 1 check digit
Swiss ISIN prefix: CH (e.g. CH0012221716 for Nestlé registered shares)

VALOR Number:
Swiss national securities identifier, 6–9 digits (e.g. 1222171 for Nestlé).
The VALOR is the primary identifier in the SECOM settlement system.
ISIN is derived from the VALOR for Swiss securities: CH + zero-padded VALOR + check digit.

Assignment Process:
1. Issuer or paying agent submits the ISINRequest form via the SIX Issuance Portal.
2. Reference Data team validates the instrument type, issuer LEI, and maturity details.
3. ISIN and VALOR are assigned within 1 business day for standard instruments;
   complex structured products may require 3 business days.
4. New ISINs are disseminated to data consumers via the SIX Financial Information
   feed (FTP / API) within 2 hours of assignment.
5. ANNA (Association of National Numbering Agencies) is notified same day.

Modification and Cancellation:
ISIN cancellation requests require written justification from the issuer.
ISINs can only be cancelled if no trades or settlements have been recorded against them.
Modification of key instrument attributes (currency, maturity) requires a new ISIN.

Common Errors:
- Incorrect LEI on the application → delays assignment; LEI must be active in GLEIF database.
- Currency mismatch between prospectus and application form.
- Missing FISN (Financial Instrument Short Name) field for structured products.
"""),

    # ── MiFIR / FINMA Regulatory Reporting ───────────────────────────────────
    dict(domain="Legal", access="internal",
         title="MiFIR Transaction Reporting — Obligations and Process",
         text="""
Under MiFIR (Markets in Financial Instruments Regulation) Article 26, investment firms
and systematic internalisers must report every transaction in financial instruments
admitted to trading on EU/EEA regulated markets to their competent authority.

SIX Swiss Exchange's Role:
SIX Swiss Exchange operates the Approved Reporting Mechanism (ARM) service
that allows participants to delegate their MiFIR reporting obligations.
The ARM service submits transaction reports to ESMA's Financial Instruments
Transparency System (FITRS) on behalf of the reporting firm.

Report Content (65 mandatory fields):
Key fields include: transaction date/time, instrument ISIN, quantity, price,
counterparty LEI, buyer/seller flags, trading venue MIC code, waiver codes,
and short selling indicators.

Deadlines:
Transaction reports must be submitted by T+1 (the business day following execution).
Amendments to submitted reports: within T+2 of identifying the error.
Cancellations of erroneous reports: within T+2.

Common Rejection Codes:
  ERR-001: Invalid ISIN (instrument not in ESMA FIRDS database)
  ERR-012: Counterparty LEI expired or not found in GLEIF
  ERR-027: Price/quantity combination outside market range (potential fat-finger)
  ERR-041: Missing buyer/seller decision maker identifier for algorithmic trading

Participant Responsibility:
Even when delegating to the SIX ARM, the legal reporting obligation remains with
the investment firm. Firms must reconcile their internal trade records with the
ARM submission confirmations daily.
FINMA may impose fines of up to CHF 100,000 for systematic reporting failures.
"""),

    dict(domain="Legal", access="confidential",
         title="Market Surveillance — Suspicious Transaction and Order Reports (STORs)",
         text="""
CONFIDENTIAL — Market Surveillance Department

Under MAR (Market Abuse Regulation) Article 16 and FINMAG Art. 31, SIX Swiss Exchange
is required to detect, investigate, and report potential market abuse.

Surveillance Triggers:
  • Unusual price movement > 3 standard deviations from 30-day average
  • High order-to-trade ratio (> 10:1 in a 5-minute window)
  • Layering / spoofing patterns detected by the SMARTS surveillance system
  • Wash trading (same beneficial owner on both sides)
  • Trading immediately before a price-sensitive announcement

STOR Submission Process:
  Step 1: Surveillance analyst reviews the alert and gathers supporting data
           (order book history, client identity, news timeline).
  Step 2: Escalation to Senior Surveillance Officer if prima facie suspicion confirmed.
  Step 3: STOR drafted using the ESMA STOR template within 2 business days of
           suspicion arising.
  Step 4: STOR submitted to FINMA via the secure FINMA eService portal.
  Step 5: Case file retained for 5 years; accessible only to Surveillance and Legal.

Tipping-Off Prohibition:
Under no circumstances may the subject of a STOR be informed that a report
has been filed. Any disclosure — intentional or inadvertent — constitutes
a criminal offence under FINMAG Art. 68.

Participant Obligations:
Participants who are investment firms must independently submit STORs to their
national competent authority. SIX Exchange STORs cover trading on the exchange
only and do not substitute for participant obligations.
"""),

    # ── Incident & Change Management ─────────────────────────────────────────
    dict(domain="Technology", access="internal",
         title="IT Incident Classification and Escalation Procedure",
         text="""
SIX Group — IT Incident Management (aligned with ITIL v4)

Incident Classification:

Priority 1 (Critical):
  Definition: Complete outage of a production service affecting multiple participants
              or a single systemically important participant; financial exposure > CHF 1M.
  Response time: 15 minutes.
  Resolution target: 2 hours.
  Escalation: CTO, Head of Operations, and affected participants notified immediately.
  External communication: Status page updated within 30 minutes; regulator informed
  if outage exceeds 2 hours (FINMA notification under FinMIG Art. 29).

Priority 2 (Major):
  Definition: Significant degradation of a production service; workaround available;
              financial exposure CHF 100K–1M.
  Response time: 30 minutes.
  Resolution target: 4 hours.
  Escalation: Department Head and Service Owner.

Priority 3 (Minor):
  Definition: Limited impact; workaround available; financial exposure < CHF 100K.
  Response time: 2 hours.
  Resolution target: next business day.
  Escalation: Service Desk team lead.

Post-Incident Review (PIR):
  Required for all P1 and P2 incidents.
  PIR must be completed within 5 business days.
  Root cause, timeline, and preventive actions documented in ServiceNow.
  PIR report shared with affected participants upon request.

Change Freeze Periods:
  No production changes permitted: last 5 business days of each month (month-end
  settlement window), and the period 48 hours before/after any major regulatory event.
"""),

    # ── Participant Onboarding ────────────────────────────────────────────────
    dict(domain="Customer Service", access="internal",
         title="Participant Onboarding — SIC and euroSIC",
         text="""
SIX Interbank Clearing — New Participant Onboarding Guide

Eligibility:
Participants in SIC must hold a Giro account at the Swiss National Bank (SNB).
For euroSIC, participants must hold a euro account with SIX and demonstrate
SWIFT connectivity with the BIC registered in the SWIFT BIC directory.

Onboarding Steps:

Phase 1 — Legal and Compliance (Week 1–2):
  • Submit signed Participation Agreement and Technical Annex.
  • Provide LEI (Legal Entity Identifier) — must be active and renewed annually.
  • AML/KYC documentation: beneficial ownership, board resolution, audited financials.
  • Compliance review by SIX Legal; approval required before proceeding to Phase 2.

Phase 2 — Technical Setup (Week 3–4):
  • SIX assigns BIC and routing configuration in SIC/euroSIC.
  • Connectivity test: participant establishes SWIFT or SIX API connection.
  • Integration testing in the SIX simulation environment (SIMEX).
  • Mandatory test scenarios: 50 payment send/receive cycles, liquidity management,
    end-of-day reconciliation, and one simulated failure scenario.

Phase 3 — Go-Live (Week 5):
  • Production access granted after successful SIMEX sign-off.
  • Dedicated SIX Relationship Manager assigned.
  • First live day monitored by SIX Operations; hotline support 07:00–18:30 CET.

Standard onboarding timeline: 4–6 weeks.
Expedited onboarding (2–3 weeks) available upon request; surcharge of CHF 5,000 applies.

Ongoing Requirements:
  LEI renewal: annually (GLEIF registration).
  SWIFT BIC validation: quarterly.
  Participation Agreement review: every 3 years or following regulatory change.
"""),

    dict(domain="Customer Service", access="internal",
         title="SIX SIS Custody Account Setup and Participant Rights",
         text="""
SIX SIS AG — Custody Account Onboarding for Securities Depository Participants

Account Structure:
Each participant holds one or more omnibus custody accounts in SECOM (SIX's
core settlement and custody system). Segregated accounts for end-investor
assets are available under the SECOM Individual Account service.

Account Types:
  Own Account       — participant's proprietary securities holdings
  Client Account    — pooled client assets (segregated from own holdings by law)
  Collateral Account — securities pledged as collateral for SIC Lombard or margin

Opening Requirements:
  • Signed Custody Agreement with SIX SIS.
  • SECOM User Setup Form specifying account type and nominated SECOM users.
  • SWIFT BIC for SECOM messaging (ISO 15022 / ISO 20022).
  • Defined settlement instruction deadlines (standard: T-1 17:00 for T+2 trades).

Settlement Instruction Submission:
  Via SWIFT MT54x series (MT540 Receive Free, MT541 Receive Vs Payment,
       MT542 Deliver Free, MT543 Deliver Vs Payment).
  Via SECOM online portal (manual input for non-SWIFT participants).
  Deadline for same-day settlement instructions: 08:30 CET.

Participant Rights:
  Participants may inspect their account statements at any time via SECOM portal.
  Annual account confirmation (depot confirmation) issued 31 December each year.
  In case of insolvency of SIX SIS, client assets are ring-fenced and cannot
  be used to satisfy SIX SIS creditors (Art. 37d Banking Act).

Fees:
  Account maintenance: CHF 500/year per account.
  Custody fee: CHF 2 per CHF 1M face value per day (equities); CHF 1 per CHF 1M (bonds).
  Settlement: CHF 5 per domestic instruction; CHF 15 per cross-border instruction.
"""),

    # ── SIX Swiss Exchange — Trading Operations ──────────────────────────────
    dict(domain="Operations", access="internal",
         title="SIX Swiss Exchange — Trading Halts and Suspension Procedure",
         text="""
SIX Swiss Exchange — Market Integrity: Trading Halts and Suspensions

Automatic Trading Halt (Circuit Breaker):
Triggered automatically by the trading system when the price of a security
moves beyond a predefined percentage range within a 5-minute rolling window.

Thresholds (equities):
  Dynamic range: ±3% from the reference price (last traded price).
  Static range:  ±15% from the opening auction reference price.

Duration: 5-minute halt; reopens via a 2-minute call auction.
If two halts occur within 30 minutes, the halt duration extends to 15 minutes.

Market Maker Obligations During Halt:
Market makers are released from their quoting obligations during a halt.
They must re-enter quotes within 2 minutes of the reopening call auction starting.

Regulatory Suspension:
Initiated by the Exchange Management or at the request of FINMA.
Reasons: pending price-sensitive announcement, suspected market manipulation,
         issuer insolvency proceedings, regulatory investigation.
Duration: discretionary; issuer notified within 15 minutes.
Reinstatement requires Exchange Management approval and, in regulatory cases,
FINMA confirmation.

Participant Notification:
Halts are broadcast via the SIX market data feed (tag 48 = HaltReason) within
500 milliseconds. Participants are also notified via the Exchange Participant Portal
and, for suspensions > 30 minutes, via direct phone call from Market Operations.

Reporting Obligation:
All halts > 60 minutes must be reported to FINMA on the next business day
with a root cause and timeline.
"""),

    dict(domain="Legal", access="internal",
         title="SIX Swiss Exchange — Listing Requirements for Equities",
         text="""
SIX Swiss Exchange Listing Rules — Key Requirements for Equity Admission

Minimum Listing Standards (Standard segment):
  • Equity capital: CHF 25 million minimum market capitalisation at time of listing.
  • Free float: at least 20% of shares in public hands.
  • Track record: 3 years of audited financial statements under IFRS or Swiss GAAP FER.
  • Prospectus: approved by the Swiss Financial Market Supervisory Authority (FINMA)
    or a recognised EEA competent authority under the Prospectus Regulation.

Additional Requirements for Prime Standard:
  • IFRS financial statements mandatory (Swiss GAAP FER not accepted).
  • Annual report published within 4 months of financial year-end.
  • Half-year report within 3 months of period-end.
  • Analyst day or capital markets day at least once every 2 years.
  • Quarterly trading update (revenue/volumes) within 45 days of quarter-end.

Ongoing Obligations (Continuing Listing Obligations):
  • Ad hoc publicity: price-sensitive information disclosed without delay via SIX
    regulatory news service before market open or after market close.
  • Directors' dealings: notified to SIX within 2 business days of transaction.
  • Major shareholder thresholds: disclosure at 3%, 5%, 10%, 15%, 20%, 25%,
    33⅓%, 50%, and 66⅔% (FMIA Article 120).
  • Corporate governance report: annual, aligned with the Swiss Code of Best Practice.

Delisting:
  Voluntary delisting requires shareholder approval (simple majority) and
  6 months' notice to SIX. Trading continues during the notice period.
  Involuntary delisting (by SIX) for failure to meet ongoing obligations after
  formal warning period of 60 days.
"""),
]

for doc in KB:
    chunks = ingest.ingest_text(
        doc["text"].strip(),
        title=doc["title"],
        access_level=doc["access"],
        domain=doc["domain"],
    )
    added = retrieval.index(chunks)
    print(f"  +{added:2d} chunks  [{doc['domain']:16s}]  {doc['title'][:55]}")

print(f"KB total: {retrieval.total_chunks} chunks\n")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────
print("Seeding audit log…")

def _load_users():
    try:
        data = json.load(open("data/users.json"))
        m = {}
        for u in data.get("users", []):
            m[u["role"]] = {"id": u["user_id"], "name": u["name"]}
        return m
    except Exception:
        return {
            "admin":  {"id": "u_admin",  "name": "Mohammed Saeed"},
            "expert": {"id": "u_jacob",  "name": "Jacob SIX"},
            "user":   {"id": "u_steve",  "name": "Steve John"},
        }

USERS  = _load_users()
steve  = USERS.get("user",   {"id": "u_steve", "name": "Steve John"})
admin  = USERS.get("admin",  {"id": "u_admin", "name": "Mohammed Saeed"})

CONV1, CONV2, CONV3 = uid12(), uid12(), uid12()

AUDIT = [
    # Conversation 1 — Settlement operations (3 turns)
    {
        "audit_id": uid12(), "conversation_id": CONV1,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=3, hours_ago=5),
        "model": "ollama/llama3.1:8b",
        "query": "A trade in Novartis shares failed to settle on T+2. What do we do first?",
        "answer": "On the intended settlement date (ISD), SECOM automatically retries settlement at each batch window: 07:00, 10:00, 13:00, and 15:30 CET. If none succeed, Operations must send a fail notification (SWIFT MT548) to both counterparties by ISD+1. Cash penalties begin accruing from ISD+4 at 1 basis point per day of face value for equities. The receiving participant may initiate a buy-in from ISD+4. [REF-1]",
        "confidence": {"level": "HIGH", "score": 0.92, "reason": "Procedure directly documented in the Failed Trade Management policy."},
        "token_usage": {"prompt_tokens": 1180, "completion_tokens": 290, "total_tokens": 1470, "estimated": False},
        "citations": [{"ref_id": "REF-1", "chunk_id": uid12(), "source_file": "Failed Trade Management and Buy-In Procedure", "author": "Operations", "domain": "Operations", "access_level": "internal", "page_number": 1, "relevant_quote": "Day ISD+0: Auto-retry at each SECOM settlement batch. Day ISD+4: Cash penalty accrual begins."}],
        "retrieval_trace": [],
    },
    {
        "audit_id": uid12(), "conversation_id": CONV1,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=3, hours_ago=4),
        "model": "ollama/llama3.1:8b",
        "query": "The counterparty wants to initiate a buy-in. What is the process and how much does SIX charge?",
        "answer": "The receiving participant appoints a buy-in agent within 2 business days of initiating the buy-in. The agent must execute the buy-in within 4 business days. If the buy-in is unsuccessful, the trade is cash-compensated at the last available market price. SIX SIS charges a buy-in administration fee of CHF 500 per transaction. [REF-1]",
        "confidence": {"level": "HIGH", "score": 0.94, "reason": "Buy-in fees and timeline explicitly stated in the CSDR procedure document."},
        "token_usage": {"prompt_tokens": 1100, "completion_tokens": 210, "total_tokens": 1310, "estimated": False},
        "citations": [{"ref_id": "REF-1", "chunk_id": uid12(), "source_file": "Failed Trade Management and Buy-In Procedure", "author": "Operations", "domain": "Operations", "access_level": "internal", "page_number": 1, "relevant_quote": "SIX SIS charges a buy-in administration fee of CHF 500 per transaction."}],
        "retrieval_trace": [],
    },
    {
        "audit_id": uid12(), "conversation_id": CONV1,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=3, hours_ago=3),
        "model": "ollama/llama3.1:8b",
        "query": "When does FINMA need to be informed about our overall fail rates?",
        "answer": "SIX SIS reports all settlement fail data to FINMA monthly via the CSDR fail rate report. Participants whose fail rate exceeds 1% receive a formal notification from SIX SIS. Individual incidents resulting in a platform outage exceeding 2 hours must be reported to FINMA under FinMIG Art. 29 on the same day. [REF-1]",
        "confidence": {"level": "HIGH", "score": 0.89, "reason": "Reporting obligations stated in the failed trade policy; FinMIG reference is accurate."},
        "token_usage": {"prompt_tokens": 1050, "completion_tokens": 195, "total_tokens": 1245, "estimated": False},
        "citations": [{"ref_id": "REF-1", "chunk_id": uid12(), "source_file": "Failed Trade Management and Buy-In Procedure", "author": "Operations", "domain": "Operations", "access_level": "internal", "page_number": 1, "relevant_quote": "All fail data is reported to FINMA monthly via the CSDR fail rate report."}],
        "retrieval_trace": [],
    },
    # Conversation 2 — Participant onboarding query (2 turns)
    {
        "audit_id": uid12(), "conversation_id": CONV2,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=1, hours_ago=6),
        "model": "ollama/llama3.1:8b",
        "query": "How long does it take to onboard a new bank to SIC and what documents do they need?",
        "answer": "Standard SIC onboarding takes 4–6 weeks in three phases. Phase 1 (weeks 1–2): legal and compliance — signed Participation Agreement, active LEI, AML/KYC documentation (beneficial ownership, board resolution, audited financials). Phase 2 (weeks 3–4): technical setup — SWIFT/API connectivity and 50-cycle testing in the SIMEX simulation environment. Phase 3 (week 5): go-live with first-day monitoring by SIX Operations. Expedited onboarding in 2–3 weeks is available for a CHF 5,000 surcharge. [REF-1]",
        "confidence": {"level": "HIGH", "score": 0.96, "reason": "Onboarding timeline and document list explicitly detailed in the participant onboarding guide."},
        "token_usage": {"prompt_tokens": 1240, "completion_tokens": 310, "total_tokens": 1550, "estimated": False},
        "citations": [{"ref_id": "REF-1", "chunk_id": uid12(), "source_file": "Participant Onboarding — SIC and euroSIC", "author": "Customer Service", "domain": "Customer Service", "access_level": "internal", "page_number": 1, "relevant_quote": "Standard onboarding timeline: 4–6 weeks. Expedited onboarding (2–3 weeks) available; surcharge of CHF 5,000."}],
        "retrieval_trace": [],
    },
    {
        "audit_id": uid12(), "conversation_id": CONV2,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=1, hours_ago=5),
        "model": "ollama/llama3.1:8b",
        "query": "The bank's LEI expired last month. Can we proceed with Phase 1?",
        "answer": "No — an active LEI is a mandatory prerequisite for Phase 1 compliance approval. An expired LEI means the legal entity cannot be properly identified or validated in the GLEIF database. The bank must renew their LEI before SIX Legal can complete the compliance review. Once the LEI is active again, Phase 1 can proceed. Ongoing LEI renewal is also an annual requirement for existing participants. [REF-1]",
        "confidence": {"level": "HIGH", "score": 0.91, "reason": "LEI requirement explicitly stated in the onboarding guide; GLEIF database reference is accurate."},
        "token_usage": {"prompt_tokens": 1100, "completion_tokens": 240, "total_tokens": 1340, "estimated": False},
        "citations": [{"ref_id": "REF-1", "chunk_id": uid12(), "source_file": "Participant Onboarding — SIC and euroSIC", "author": "Customer Service", "domain": "Customer Service", "access_level": "internal", "page_number": 1, "relevant_quote": "Provide LEI (Legal Entity Identifier) — must be active and renewed annually."}],
        "retrieval_trace": [],
    },
    # Conversation 3 — Greeting + MiFIR reporting question + off-topic (3 turns)
    {
        "audit_id": uid12(), "conversation_id": CONV3,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(hours_ago=4),
        "model": "ollama/llama3.1:8b",
        "query": "Good morning!",
        "answer": "Good morning! I'm AskMe, SIX Group's internal knowledge assistant. I can help you with operational procedures, regulatory requirements, participant onboarding, reference data, and more. What can I help you with today?",
        "confidence": {"level": "HIGH", "score": 1.0, "reason": "Conversational response."},
        "token_usage": {"prompt_tokens": 118, "completion_tokens": 52, "total_tokens": 170, "estimated": False},
        "citations": [], "retrieval_trace": [],
    },
    {
        "audit_id": uid12(), "conversation_id": CONV3,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(hours_ago=3),
        "model": "ollama/llama3.1:8b",
        "query": "A participant received ERR-012 when submitting a MiFIR transaction report. What does that mean?",
        "answer": "ERR-012 means the counterparty LEI is either expired or not found in the GLEIF database. The participant must verify their counterparty's LEI is active and valid in GLEIF before resubmitting. The amendment must be filed within T+2 of identifying the error. Note that even when using the SIX ARM for reporting, the legal responsibility for accurate and timely reporting remains with the investment firm — FINMA may impose fines of up to CHF 100,000 for systematic reporting failures. [REF-1]",
        "confidence": {"level": "HIGH", "score": 0.93, "reason": "Error code meaning and amendment deadline explicitly documented in the MiFIR reporting guide."},
        "token_usage": {"prompt_tokens": 1280, "completion_tokens": 270, "total_tokens": 1550, "estimated": False},
        "citations": [{"ref_id": "REF-1", "chunk_id": uid12(), "source_file": "MiFIR Transaction Reporting — Obligations and Process", "author": "Legal", "domain": "Legal", "access_level": "internal", "page_number": 1, "relevant_quote": "ERR-012: Counterparty LEI expired or not found in GLEIF."}],
        "retrieval_trace": [],
    },
    {
        "audit_id": uid12(), "conversation_id": CONV3,
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(hours_ago=2),
        "model": "ollama/llama3.1:8b",
        "query": "Thanks, that helped a lot!",
        "answer": "You're welcome! Feel free to ask anytime you need help with SIX Group procedures or regulatory requirements. Have a great day!",
        "confidence": {"level": "HIGH", "score": 1.0, "reason": "Conversational response."},
        "token_usage": {"prompt_tokens": 115, "completion_tokens": 38, "total_tokens": 153, "estimated": False},
        "citations": [], "retrieval_trace": [],
    },
    # Two LOW-confidence entries that generate tickets
    {
        "audit_id": "demo_low_001", "conversation_id": uid12(),
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=5, hours_ago=2),
        "model": "ollama/llama3.1:8b",
        "query": "What is the procedure for handling a SIC participant that requests an emergency intraday credit extension beyond their Lombard limit?",
        "answer": "The knowledge base covers standard Lombard credit procedures but does not contain a specific policy for emergency intraday credit extensions beyond the approved limit. Please contact the SIX Operations team or the SNB liaison desk directly for guidance on this exceptional situation.",
        "confidence": {"level": "LOW", "score": 0.0, "reason": "Emergency credit extension beyond Lombard limit not documented in available knowledge base."},
        "token_usage": {"prompt_tokens": 920, "completion_tokens": 115, "total_tokens": 1035, "estimated": False},
        "citations": [], "retrieval_trace": [],
    },
    {
        "audit_id": "demo_low_002", "conversation_id": uid12(),
        "user_id": steve["id"], "user_name": steve["name"],
        "timestamp": ts(days_ago=6, hours_ago=3),
        "model": "ollama/llama3.1:8b",
        "query": "How do we process a corporate action event where the issuer has gone into insolvency proceedings mid-event?",
        "answer": "The standard corporate actions processing guide does not cover insolvency scenarios during an in-flight event. This is a complex legal and operational edge case. Please escalate immediately to the SIX SIS Corporate Actions team lead and the Legal department for case-specific guidance.",
        "confidence": {"level": "LOW", "score": 0.0, "reason": "Insolvency-during-corporate-action scenario not covered in the knowledge base."},
        "token_usage": {"prompt_tokens": 880, "completion_tokens": 108, "total_tokens": 988, "estimated": False},
        "citations": [], "retrieval_trace": [],
    },
]

with open("audit_log.jsonl", "w", encoding="utf-8") as f:
    for e in AUDIT:
        f.write(json.dumps(e) + "\n")
print(f"  Written {len(AUDIT)} audit entries")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  TRAINING QUESTIONS
# ─────────────────────────────────────────────────────────────────────────────
print("\nSeeding training questions…")

QUESTIONS = [

    # ── Operations / Settlement ──────────────────────────────────────────────
    {
        "domain": "Operations", "difficulty": "easy",
        "situation": "It is 09:30 CET on a Tuesday. A participant calls to say their equity trade in ABB Ltd has not settled and the intended settlement date was yesterday (Monday). What are the first three steps you take?",
        "expected_answer": "First, check SECOM to confirm the fail status and see if the 07:00 and the upcoming 10:00 retry batches have been or will be attempted. Second, verify whether both counterparties have submitted matching settlement instructions — a common cause of fails is mismatched instructions (wrong ISIN, quantity, or price). Third, send a SWIFT MT548 fail notification to both counterparties today (ISD+1) if the retry batches do not resolve the fail. Also inform both parties that cash penalties will begin accruing from ISD+4 at 1 bp/day."
    },
    {
        "domain": "Operations", "difficulty": "medium",
        "situation": "A participant's equity trade in Roche has been failing for 5 business days. The counterparty now wants to initiate a buy-in. Walk through the complete buy-in process including what happens if the buy-in itself fails.",
        "expected_answer": "Since it is ISD+5 (beyond the ISD+4 threshold for equities), the receiving participant is entitled to initiate a buy-in. They appoint a buy-in agent within 2 business days. The agent executes the buy-in within 4 business days. SIX SIS charges a CHF 500 administration fee. If the buy-in is unsuccessful (e.g. no securities available in the market), the trade must be cash-compensated at the last available market price — the delivering participant pays the difference if the market price exceeds the original trade price. Cash penalties continue to accrue throughout the process. The entire case must be documented and will be included in the monthly CSDR fail report submitted to FINMA."
    },
    {
        "domain": "Operations", "difficulty": "easy",
        "situation": "A newly listed company's shares need an ISIN. The issuer's agent has submitted the ISINRequest form but the LEI on the form is listed as 'PENDING' in the GLEIF database. Can you assign the ISIN now?",
        "expected_answer": "No — the LEI must be active in the GLEIF database before the ISIN can be assigned. A pending LEI means the legal entity has not yet completed its LEI registration, and SIX cannot validate the issuer's identity. Contact the issuer's agent and ask them to complete their LEI registration and confirm once it is active in GLEIF. Standard ISIN assignment can then proceed within 1 business day."
    },
    {
        "domain": "Operations", "difficulty": "hard",
        "situation": "During end-of-day settlement in SECOM, a major bank (accounting for 15% of daily settlement volume) experiences a technical failure and cannot deliver settlement instructions. The cut-off is in 30 minutes. What is your escalation path and what can be done operationally?",
        "expected_answer": "Immediately escalate to the SIX SIS Operations duty manager and the Head of Payment Services — this qualifies as at least a Priority 2 incident given the systemic volume involved. Notify the affected participant of the situation. Operationally, explore whether the participant can submit instructions via the SECOM online portal (manual fallback) if their SWIFT connection has failed. If no instructions can be received before cut-off, all trades for that participant will fail and settlement penalties begin from ISD+4. Document everything in ServiceNow and prepare a Post-Incident Review. If the disruption lasts more than 2 hours and affects overall system stability, escalate to the CTO and prepare a FINMA notification under FinMIG Art. 29."
    },

    # ── SIC / Payments ───────────────────────────────────────────────────────
    {
        "domain": "Operations", "difficulty": "medium",
        "situation": "A SIC participant is reporting that a high-priority payment of CHF 500M to the SNB is stuck in the queue despite them having sufficient Lombard collateral. It is 15:00 CET — 30 minutes before the interbank cut-off. What do you investigate and what actions are available?",
        "expected_answer": "First, log into the SIC Participant Interface and check the payment's priority class — verify it is set to Priority 1 (SNB transactions) or at minimum Priority 2. If it is incorrectly queued at a lower priority, work with the participant to reassign it. Check whether there is a gridlock situation — the next optimisation run is in less than 30 minutes, which may resolve circular dependencies. If time is critical, a manual liquidity injection or bilateral agreement between participants can be explored with SNB support. Given the size (CHF 500M) and the proximity to the 17:30 interbank cut-off, escalate to the SIC Operations manager immediately. Payments not settled by 17:30 are returned to the sender."
    },
    {
        "domain": "Operations", "difficulty": "easy",
        "situation": "A participant wants to send a EUR 120,000 SEPA Instant Credit Transfer via euroSIC. The client says it should arrive instantly. Can this be processed and is there anything to check?",
        "expected_answer": "There is a problem — the SEPA Instant maximum amount via euroSIC is EUR 100,000. A EUR 120,000 payment exceeds this limit and cannot be processed as a SEPA Instant Credit Transfer. The participant has two options: (1) split it into two SEPA Instant transactions of EUR 100,000 or less each, or (2) process it as a standard SEPA Credit Transfer, which settles on the next business day rather than instantly. Inform the client of the limitation and agree on the preferred approach."
    },

    # ── Regulatory Reporting ─────────────────────────────────────────────────
    {
        "domain": "Legal", "difficulty": "medium",
        "situation": "A participant using the SIX ARM for MiFIR reporting discovers on Wednesday that a batch of 200 transaction reports submitted the previous Monday contained an incorrect counterparty LEI (ERR-012). What must they do and by when?",
        "expected_answer": "The participant must submit amendments for all 200 affected reports. Under MiFIR, amendments must be filed within T+2 of identifying the error — since they identified the error on Wednesday, amendments are due by Friday. The process involves cancelling the original erroneous reports and submitting corrected ones via the SIX ARM. Even though SIX ARM submits on their behalf, the legal obligation and liability for accurate reporting remain with the investment firm. They should also check their daily reconciliation between internal trade records and ARM submission confirmations — this error should have been caught sooner. Document the incident in case FINMA asks for an explanation."
    },
    {
        "domain": "Legal", "difficulty": "hard",
        "situation": "Your market surveillance system flags an unusual trading pattern: a client placed and cancelled large orders in a Zurich-listed stock 47 times in 2 hours, then executed a small position just before a price increase. The order-to-trade ratio is 15:1. What is the process from here?",
        "expected_answer": "This pattern — high order-to-trade ratio (15:1 vs. the 10:1 threshold) combined with possible front-running — triggers a STOR (Suspicious Transaction and Order Report) investigation under MAR Article 16. The surveillance analyst reviews the full order book history, client identity, and any price-sensitive news timeline around the relevant period. If prima facie suspicion is confirmed, escalate to the Senior Surveillance Officer immediately. A STOR must be drafted using the ESMA template and submitted to FINMA via the secure eService portal within 2 business days of the suspicion arising. Critical: under no circumstances may the client be informed that a STOR has been filed — doing so constitutes a tipping-off offence under FINMAG Art. 68 and is a criminal offence. All case files must be retained for 5 years."
    },

    # ── Incident Management ──────────────────────────────────────────────────
    {
        "domain": "Technology", "difficulty": "medium",
        "situation": "At 09:15 CET, the SIC system becomes completely unreachable for all participants. You are the incident coordinator. It is now 09:30 and there is no resolution in sight. Walk through your response actions.",
        "expected_answer": "A complete SIC outage affecting all participants is a Priority 1 (Critical) incident. Response time target is 15 minutes — you are already at 15 minutes so the P1 clock is running. Immediately notify the CTO, Head of Operations, and all affected participants. Update the SIX status page within 30 minutes. Assemble the technical incident team in a bridge call. Since the outage has now reached 15 minutes with no resolution in sight, prepare for the 2-hour FINMA notification threshold under FinMIG Art. 29 — have the notification template ready. All payments queued during the outage period will need to be processed once the system recovers; work with Operations to manage the backlog. After resolution, a Post-Incident Review must be completed within 5 business days."
    },
    {
        "domain": "Technology", "difficulty": "easy",
        "situation": "A team member wants to deploy a configuration change to the production payment routing system on the last business day of the month at 14:00 CET. Is this permitted under SIX change management policy?",
        "expected_answer": "No — the last 5 business days of each month fall within the change freeze period (month-end settlement window) during which no production changes are permitted. The deployment must be rescheduled to after the month-end window closes. If the change is critical (e.g. a security patch or regulatory mandate), an exception request must be submitted to the Change Advisory Board with documented justification. Standard changes and improvements must simply wait until the freeze period ends."
    },

    # ── Customer Service / Participant Relations ──────────────────────────────
    {
        "domain": "Customer Service", "difficulty": "medium",
        "situation": "A bank applying for SIC participation has completed Phases 1 and 2 but during SIMEX testing only completed 38 of the mandatory 50 payment cycles before their team ran out of time. Their Head of Treasury is pushing to go live next week. Can you approve go-live?",
        "expected_answer": "No — go-live cannot be approved until all 50 mandatory payment cycles are successfully completed in SIMEX, along with the liquidity management, end-of-day reconciliation, and simulated failure scenario tests. This is a mandatory requirement, not a guideline. Explain to the participant that SIMEX sign-off is a pre-condition for production access without exception. Offer to schedule additional SIMEX test sessions as soon as possible to help them complete the remaining 12 cycles. If they are under time pressure, remind them that the expedited onboarding option (with CHF 5,000 surcharge) was available upfront to compress the testing window — but all test requirements still apply."
    },
    {
        "domain": "Customer Service", "difficulty": "easy",
        "situation": "A participant contacts you because they did not elect on a rights issue by the election deadline. They are asking SIX SIS to process a late election on their behalf.",
        "expected_answer": "Late elections cannot be accepted — the election deadline for voluntary corporate actions is firm and SIX SIS cannot override it. For rights issues, unexercised rights are sold in the rump auction and the net cash proceeds are credited to the participant's account. This is the standard outcome for participants who miss the deadline. Explain this clearly to the participant, confirm when the rump auction proceeds will be credited (typically around the payment date), and advise them to review their election management process to prevent this in future. Also remind them that entitlement discrepancies must be reported within 3 business days of any credit/debit notification."
    },
]

with open("data/training_questions.jsonl", "w", encoding="utf-8") as f:
    for q in QUESTIONS:
        entry = {
            "question_id":     uid12(),
            "domain":          q["domain"],
            "difficulty":      q["difficulty"],
            "situation":       q["situation"],
            "expected_answer": q["expected_answer"],
            "created_by":      admin.get("id", "u_admin"),
            "created_by_name": "Mohammed Saeed",
            "created_at":      ts(days_ago=7),
        }
        f.write(json.dumps(entry) + "\n")
print(f"  Written {len(QUESTIONS)} training questions")


# ─────────────────────────────────────────────────────────────────────────────
# 4.  TICKETS
# ─────────────────────────────────────────────────────────────────────────────
print("\nSeeding tickets…")

TICKETS = [
    {
        "ticket_id":        uid12(),
        "query":            "What is the procedure for handling a SIC participant that requests an emergency intraday credit extension beyond their Lombard limit?",
        "answer":           "The knowledge base covers standard Lombard credit procedures but does not contain a specific policy for emergency intraday credit extensions beyond the approved limit.",
        "confidence_level": "LOW", "confidence_reason": "Emergency credit extension beyond Lombard limit not documented.",
        "domain": "Operations", "no_data": True, "status": "open",
        "user_id": steve["id"], "user_name": steve["name"],
        "audit_id": "demo_low_001", "created_at": ts(days_ago=5, hours_ago=2),
    },
    {
        "ticket_id":        uid12(),
        "query":            "How do we process a corporate action event where the issuer has gone into insolvency proceedings mid-event?",
        "answer":           "The standard corporate actions guide does not cover insolvency scenarios during an in-flight event.",
        "confidence_level": "LOW", "confidence_reason": "Insolvency-during-corporate-action scenario not covered.",
        "domain": "Operations", "no_data": True, "status": "open",
        "user_id": steve["id"], "user_name": steve["name"],
        "audit_id": "demo_low_002", "created_at": ts(days_ago=6, hours_ago=3),
    },
    {
        "ticket_id":        uid12(),
        "query":            "What is the SIX policy on handling ISO 20022 migration failures where a participant submits legacy MT messages after the CBPR+ deadline?",
        "answer":           "The knowledge base does not yet include the ISO 20022 CBPR+ migration cutover policy and fallback procedures.",
        "confidence_level": "LOW", "confidence_reason": "ISO 20022 migration fallback procedures not in knowledge base.",
        "domain": "Technology", "no_data": True, "status": "open",
        "user_id": steve["id"], "user_name": steve["name"],
        "audit_id": None, "created_at": ts(days_ago=2, hours_ago=4),
    },
    {
        "ticket_id":        uid12(),
        "query":            "How long must SIX retain records of STOR submissions to FINMA?",
        "answer":           "Based on the market surveillance document, STOR case files must be retained for 5 years, accessible only to Surveillance and Legal departments.",
        "confidence_level": "LOW", "confidence_reason": "Answer found but confidence was low due to limited corroborating sources.",
        "domain": "Legal", "no_data": False, "status": "resolved",
        "user_id": steve["id"], "user_name": steve["name"],
        "audit_id": None, "created_at": ts(days_ago=8, hours_ago=1),
    },
]

with open("data/tickets.jsonl", "w", encoding="utf-8") as f:
    for t in TICKETS:
        f.write(json.dumps(t) + "\n")
print(f"  Written {len(TICKETS)} tickets")


# ─────────────────────────────────────────────────────────────────────────────
# 5.  USER PROGRESS (Steve John's training history)
# ─────────────────────────────────────────────────────────────────────────────
print("\nSeeding user progress…")

PROGRESS = [
    {"days_ago": 7, "domain": "Operations",
     "score": 50, "feedback": "You identified the fail notification requirement but missed the automatic retry batches that happen before manual action is needed.",
     "strengths": ["Correctly identified the MT548 fail notification"],
     "improvements": ["SECOM retries automatically at 4 batch windows on ISD — check those first before escalating"]},

    {"days_ago": 7, "domain": "Legal",
     "score": 62, "feedback": "Good awareness of STOR requirements but the tipping-off prohibition is critical and was not mentioned.",
     "strengths": ["Knew the 2-business-day STOR submission deadline"],
     "improvements": ["Never forget: informing the subject of a STOR is a criminal offence under FINMAG Art. 68"]},

    {"days_ago": 5, "domain": "Operations",
     "score": 74, "feedback": "Solid understanding of the buy-in process. You got the timeline right but omitted the CHF 500 SIX SIS administration fee.",
     "strengths": ["Correct ISD+4 trigger date for equities", "Covered cash compensation for failed buy-ins"],
     "improvements": ["Include the CHF 500 buy-in administration fee charged by SIX SIS"]},

    {"days_ago": 5, "domain": "Technology",
     "score": 68, "feedback": "You correctly identified the change freeze window but did not mention the exception process for critical changes.",
     "strengths": ["Correctly identified month-end freeze period (last 5 business days)"],
     "improvements": ["Critical changes (security patches, regulatory mandates) can proceed via Change Advisory Board exception request"]},

    {"days_ago": 3, "domain": "Customer Service",
     "score": 82, "feedback": "Excellent answer on participant onboarding. All phases covered correctly and you cited the CHF 5,000 expedited surcharge.",
     "strengths": ["All 3 onboarding phases described accurately", "Mentioned the expedited onboarding option and surcharge"],
     "improvements": ["Could mention that LEI must be renewed annually as an ongoing obligation"]},

    {"days_ago": 3, "domain": "Operations",
     "score": 85, "feedback": "Strong answer on the SEPA Instant limit. Clear explanation and practical alternatives offered.",
     "strengths": ["Correctly cited the EUR 100,000 SEPA Instant maximum", "Offered two practical alternatives to the client"],
     "improvements": ["Mention that standard SEPA Credit Transfer settles next business day — useful context for the client"]},

    {"days_ago": 1, "domain": "Legal",
     "score": 88, "feedback": "Very good MiFIR amendment answer. Covered the T+2 amendment deadline and the legal responsibility of the investment firm.",
     "strengths": ["Correct T+2 amendment deadline cited", "Correctly noted that ARM delegation does not transfer legal liability"],
     "improvements": ["Recommend that participants check daily reconciliation — the error should have been caught sooner"]},

    {"days_ago": 0, "domain": "Technology",
     "score": 93, "feedback": "Outstanding P1 incident response. All escalation steps in the right order, including the 2-hour FINMA notification threshold.",
     "strengths": ["Correct P1 classification and 15-minute response target", "Remembered the FINMA notification under FinMIG Art. 29", "Mentioned the Post-Incident Review requirement"],
     "improvements": ["Could also mention preparing a participant communication template in advance to save time during the crisis"]},
]

with open("data/user_progress.jsonl", "w", encoding="utf-8") as f:
    for p in PROGRESS:
        entry = {
            "user_id":      steve["id"],
            "question_id":  uid12(),
            "domain":       p["domain"],
            "score":        p["score"],
            "feedback":     p["feedback"],
            "strengths":    p["strengths"],
            "improvements": p["improvements"],
            "date":         today_minus(p["days_ago"]),
            "timestamp":    (NOW - timedelta(days=p["days_ago"], hours=2)).isoformat(),
        }
        f.write(json.dumps(entry) + "\n")
print(f"  Written {len(PROGRESS)} progress entries")

print("\n✓ Done")
print(f"  KB chunks      : {retrieval.total_chunks}")
print(f"  Audit entries  : {len(AUDIT)}")
print(f"  Training Qs    : {len(QUESTIONS)}")
print(f"  Tickets        : {len(TICKETS)}")
print(f"  Progress recs  : {len(PROGRESS)}")
