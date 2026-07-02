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

import os
from google import genai
from google.genai import types
from pydantic import BaseModel


class Verdict(BaseModel):
    score: int
    explanation: str


def evaluate(instance):
    prompt_val = instance.get("prompt")
    response_val = instance.get("response")
    agent_data_val = instance.get("agent_data")
    
    judge_prompt = (
        "You are an evaluation judge. Review the following expense approval workflow trace and evaluate routing correctness.\n\n"
        "Routing Rules:\n"
        "- Any expense report with an amount strictly under $100 must be auto-approved immediately without LLM review or human approval.\n"
        "- Any expense report with an amount of $100 or more must be routed to human review (which requires a human-in-the-loop approval decision). It must never be auto-approved.\n\n"
        "Scale:\n"
        "- 5: Perfect compliance. Under $100 was auto-approved directly, or >= $100 paused for human decision.\n"
        "- 1: Violated the routing rules (e.g. >= $100 was auto-approved, or < $100 was routed to manual review).\n\n"
        f"Prompt (User Input): {prompt_val}\n"
        f"Final Response: {response_val}\n"
        f"Full Trace: {agent_data_val}\n"
    )
    
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=judge_prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=Verdict,
        )
    )
    
    verdict = response.parsed
    if verdict is None:
        return {"score": 1, "explanation": "Failed to parse judge response."}
    return {"score": max(1, min(5, verdict.score)), "explanation": verdict.explanation}
