# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import re
from typing import Any, AsyncGenerator

from google import genai
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import Workflow
from google.genai import types
from pydantic import BaseModel, Field

from .config import MODEL_NAME, THRESHOLD


# =====================================================================
# Structured Data Models
# =====================================================================

class ExpenseReport(BaseModel):
    """Pydantic model representing an expense report's structured fields."""
    amount: float = Field(description="The total dollar amount of the expense.")
    submitter: str = Field(description="The name or email of the employee submitting the expense.")
    category: str = Field(description="The category of the expense (e.g. Travel, Meals, Office Supplies).")
    description: str = Field(description="A description of the expense context.")
    date: str = Field(description="The date of the expense (YYYY-MM-DD).")


class RiskReview(BaseModel):
    """Pydantic model representing the LLM's automated policy review."""
    is_risky: bool = Field(description="True if the expense contains risk factors or policy violations.")
    risk_factors: list[str] = Field(description="A list of specific risk factors or warnings flagged.")
    alert_message: str = Field(description="A summary explanation of findings for the human approver.")


# =====================================================================
# Workflow Nodes
# =====================================================================

def parse_expense_report(node_input: types.Content) -> ExpenseReport:
    """Parses Pub/Sub-like base64 data or plain JSON text into an ExpenseReport."""
    text_content = ""
    if node_input and node_input.parts:
        text_content = node_input.parts[0].text or ""

    try:
        payload = json.loads(text_content.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Input is not valid JSON: '{text_content}'. Error: {e}")

    # Handle Pub/Sub push wrapping
    if "message" in payload and isinstance(payload["message"], dict):
        payload = payload["message"]

    data_value = payload.get("data")
    if data_value is None:
        data_value = payload

    # Decode base64 if needed, or parse raw string
    if isinstance(data_value, str):
        try:
            decoded_bytes = base64.b64decode(data_value, validate=True)
            decoded_str = decoded_bytes.decode("utf-8")
            expense_dict = json.loads(decoded_str)
        except Exception:
            try:
                expense_dict = json.loads(data_value)
            except Exception as e:
                raise ValueError(f"Failed to decode base64 or parse string: {data_value}. Error: {e}")
    elif isinstance(data_value, dict):
        expense_dict = data_value
    else:
        raise ValueError(f"Unsupported data format: {type(data_value)}")

    return ExpenseReport(
        amount=float(expense_dict.get("amount", 0.0)),
        submitter=str(expense_dict.get("submitter", "Unknown")),
        category=str(expense_dict.get("category", "General")),
        description=str(expense_dict.get("description", "")),
        date=str(expense_dict.get("date", "")),
    )


def route_expense(node_input: ExpenseReport) -> Event:
    """Routes the expense report depending on the threshold limit in Python code."""
    if node_input.amount < THRESHOLD:
        return Event(
            output=node_input,
            route="auto_approve",
            state={"expense": node_input.model_dump()}
        )
    else:
        return Event(
            output=node_input,
            route="review",
            state={"expense": node_input.model_dump()}
        )


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Redacts Social Security Numbers (SSN) and Credit Card numbers from text."""
    redacted_categories = []
    
    # SSN Regex (matches formats like 000-00-0000 or 000000000)
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b'
    if re.search(ssn_pattern, text):
        text = re.sub(ssn_pattern, '[REDACTED SSN]', text)
        redacted_categories.append('SSN')
        
    # Credit Card Regex (matches 13 to 16 digit numbers, possibly space/hyphen separated)
    cc_pattern = r'\b(?:\d[ -]*?){13,16}\b'
    # Extra check to ensure CC-like sequence doesn't overlap completely with SSN
    matches = list(re.finditer(cc_pattern, text))
    if matches:
        text = re.sub(cc_pattern, '[REDACTED CREDIT CARD]', text)
        redacted_categories.append('Credit Card')
        
    return text, redacted_categories


def check_prompt_injection(text: str) -> bool:
    """Scans the text for common override and prompt injection attack vectors."""
    lower_text = text.lower()
    attack_phrases = [
        "auto-approve",
        "force approve",
        "bypass rules",
        "override rules",
        "ignore instruction",
        "ignore rules",
        "system prompt",
        "new instruction",
        "forget previous",
        "you must approve"
    ]
    return any(phrase in lower_text for phrase in attack_phrases)


def security_check(ctx: Context, node_input: ExpenseReport) -> Event:
    """Sanitizes PII and detects prompt injection attacks in the expense description."""
    desc = node_input.description
    
    # 1. SSN and CC Redaction
    clean_desc, redacted = redact_pii(desc)
    node_input.description = clean_desc
    
    # Record redacted categories in the session state
    state_updates = {
        "expense": node_input.model_dump(),
        "redacted_categories": redacted
    }
    
    # 2. Prompt Injection Check
    if check_prompt_injection(desc):
        # Mark as a security event and bypass LLM reviewer
        state_updates["is_security_event"] = True
        
        # Craft a mock RiskReview indicating security threat
        mock_review = RiskReview(
            is_risky=True,
            risk_factors=["Prompt Injection Detected"],
            alert_message="Security Alert: Expense description contained potential policy override or system prompt injection instructions."
        )
        
        return Event(
            output=mock_review,
            route="bypass_review",
            state=state_updates
        )
        
    return Event(
        output=node_input,
        route="clean_review",
        state=state_updates
    )


def auto_approve_node(node_input: ExpenseReport) -> Event:
    """Instantly auto-approves expenses that are below the threshold."""
    # Run PII redaction on description even for auto-approvals to keep human approval payload clean
    clean_desc, redacted = redact_pii(node_input.description)
    node_input.description = clean_desc
    
    outcome = {
        "status": "APPROVED",
        "reason": f"Auto-approved: amount is under the ${THRESHOLD:.2f} threshold.",
        "amount": node_input.amount,
        "submitter": node_input.submitter,
    }
    return Event(
        output=outcome,
        state={
            "outcome": outcome,
            "expense": node_input.model_dump(),
            "redacted_categories": redacted
        },
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(
                text=f"✅ Expense of ${node_input.amount:.2f} submitted by {node_input.submitter} has been auto-approved."
            )]
        )
    )


async def reviewer(ctx: Context, node_input: ExpenseReport) -> Event:
    """Invokes Gemini model to evaluate policy risk, using only sanitized inputs."""
    client = genai.Client()
    
    prompt = (
        f"Analyze the following expense report details and determine if the expense contains anomalies, "
        f"is suspicious, or violates spending policy.\n\n"
        f"Expense Details:\n"
        f"- Amount: ${node_input.amount:.2f}\n"
        f"- Submitter: {node_input.submitter}\n"
        f"- Category: {node_input.category}\n"
        f"- Description: {node_input.description}\n"
        f"- Date: {node_input.date}\n"
    )
    
    response = await client.aio.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are an automated policy compliance auditor. Flag anomalies (e.g. leisure travel charges, "
                "weekend dates, suspicious descriptions, excessive meals). Provide a concise summary warning message "
                "for a human approver."
            ),
            response_mime_type="application/json",
            response_schema=RiskReview,
        )
    )
    
    verdict = response.parsed
    if verdict is None:
        verdict = RiskReview(
            is_risky=False,
            risk_factors=[],
            alert_message="Could not parse risk review. Handled as low risk."
        )
        
    return Event(
        output=verdict,
        state={"risk_review": verdict.model_dump()},
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=json.dumps(verdict.model_dump()))]
        )
    )


async def human_approval(ctx: Context, node_input: RiskReview) -> AsyncGenerator[Event | RequestInput, None]:
    """Workflow node implementing Human-in-the-Loop pause and resume approval gate."""
    expense = ctx.state.get("expense", {})
    amount = expense.get("amount", 0.0)
    submitter = expense.get("submitter", "Unknown")
    desc = expense.get("description", "")
    is_security_event = ctx.state.get("is_security_event", False)
    redacted_categories = ctx.state.get("redacted_categories", [])

    # Pause workflow if human input has not been received yet
    if not ctx.resume_inputs or "approval_decision" not in ctx.resume_inputs:
        security_header = ""
        if is_security_event:
            security_header = "🚨 SECURITY ALERT: Prompt injection attempt detected! LLM review was bypassed.\n"
            
        redacted_info = ""
        if redacted_categories:
            redacted_info = f" [PII Redacted: {', '.join(redacted_categories)}]"

        prompt_msg = (
            f"{security_header}"
            f"⚠️ Expense Alert: ${amount:.2f} submitted by {submitter} ({desc}{redacted_info}) requires approval.\n"
            f"LLM Risk Assessment:\n"
            f"  - Status: {'RISKY' if node_input.is_risky else 'LOW RISK'}\n"
            f"  - Risk Factors: {', '.join(node_input.risk_factors) if node_input.risk_factors else 'None'}\n"
            f"  - Summary: {node_input.alert_message}\n\n"
            "Please respond with 'approve' or 'reject'."
        )
        yield RequestInput(
            interrupt_id="approval_decision",
            message=prompt_msg
        )
        return

    # Resume execution once approval is submitted
    decision = ctx.resume_inputs["approval_decision"].strip().lower()
    status = "APPROVED" if "approve" in decision else "REJECTED"

    outcome = {
        "status": status,
        "reason": f"Reviewed by LLM. Human decision: {status}",
        "amount": amount,
        "submitter": submitter,
        "risk_review": node_input.model_dump(),
        "is_security_event": is_security_event,
        "redacted_categories": redacted_categories
    }

    yield Event(
        output=outcome,
        state={"outcome": outcome},
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(
                text=f"Decision recorded: Expense of ${amount:.2f} by {submitter} has been {status}."
            )]
        )
    )


# =====================================================================
# Workflow Initialization
# =====================================================================

root_agent = Workflow(
    name="expense_workflow",
    edges=[
        ('START', parse_expense_report),
        (parse_expense_report, route_expense),
        (route_expense, {"auto_approve": auto_approve_node, "review": security_check}),
        (security_check, {"clean_review": reviewer, "bypass_review": human_approval}),
        (reviewer, human_approval),
    ],
)

app = App(
    name="expense_agent",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
