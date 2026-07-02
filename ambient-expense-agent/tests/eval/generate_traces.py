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

import json
import os
from pathlib import Path
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from expense_agent.agent import root_agent


def load_dotenv():
    """Manually parse .env file to populate environment variables."""
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    os.environ[key] = val


def main():
    load_dotenv()
    
    dataset_path = Path("tests/eval/datasets/basic-dataset.json")
    output_path = Path("artifacts/traces/generated_traces.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    eval_cases = dataset.get("eval_cases", [])
    graded_cases = []
    
    for case in eval_cases:
        case_id = case["eval_case_id"]
        prompt_content = case["prompt"]
        prompt_text = prompt_content["parts"][0]["text"]
        
        print(f"Running case: {case_id}")
        
        session_service = InMemorySessionService()
        session = session_service.create_session_sync(user_id="eval_user", app_name="expense_agent")
        runner = Runner(agent=root_agent, session_service=session_service, app_name="expense_agent")
        
        # 1. Run the initial user prompt
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_text)]
        )
        
        events = list(
            runner.run(
                new_message=message,
                user_id="eval_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        )
        
        # 2. Check if the workflow is waiting on human approval (RequestInput event)
        request_input_event = None
        for ev in events:
            if hasattr(ev, "interrupt_id"):
                request_input_event = ev
                break
                
        if request_input_event:
            print(f"  Encountered human approval gate: {request_input_event.message.strip()}")
            
            # Retrieve session state to decide approval vs rejection
            session_obj = session_service.get_session_sync(
                app_name="expense_agent", user_id="eval_user", session_id=session.id
            )
            session_state = session_obj.state if session_obj else {}
            is_security_event = session_state.get("is_security_event", False)
            
            # Automate decision: Reject if security event (prompt injection), approve otherwise
            decision = "reject" if is_security_event else "approve"
            print(f"  Automating human decision: {decision}")
            
            # Resume session with decision
            resume_message = types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id="approval_decision",
                            name="approval_decision",
                            response={"approval_decision": decision}
                        )
                    )
                ]
            )
            
            resume_events = list(
                runner.run(
                    new_message=resume_message,
                    user_id="eval_user",
                    session_id=session.id,
                    run_config=RunConfig(streaming_mode=StreamingMode.SSE),
                )
            )
            events.extend(resume_events)
            
        # Get final response text from the last text event
        final_text = ""
        for ev in reversed(events):
            if hasattr(ev, "content") and ev.content and ev.content.parts:
                for p in ev.content.parts:
                    if p.text:
                        final_text = p.text
                        break
                if final_text:
                    break
                    
        # Extract chronological conversation events from session history
        full_session = session_service.get_session_sync(
            app_name="expense_agent", user_id="eval_user", session_id=session.id
        )
        turns = []
        current_events = []
        turn_index = 0
        
        session_events = full_session.events if full_session else []
        for ev in session_events:
            author = ev.author
            if author == "eval_user" or author == "user":
                if current_events:
                    turns.append({
                        "turn_index": turn_index,
                        "events": current_events
                    })
                    turn_index += 1
                    current_events = []
                author = "user"
                
            content_dict = None
            if ev.content:
                content_dict = {
                    "role": ev.content.role or "model",
                    "parts": []
                }
                for part in ev.content.parts:
                    part_dict = {}
                    if part.text is not None:
                        part_dict["text"] = part.text
                    elif part.function_call is not None:
                        part_dict["function_call"] = {
                            "name": part.function_call.name,
                            "args": part.function_call.args
                        }
                    elif part.function_response is not None:
                        part_dict["function_response"] = {
                            "id": part.function_response.id,
                            "name": part.function_response.name,
                            "response": part.function_response.response
                        }
                    if part_dict:
                        content_dict["parts"].append(part_dict)
            else:
                continue
                
            current_events.append({
                "author": author,
                "content": content_dict
            })
            
        if current_events:
            turns.append({
                "turn_index": turn_index,
                "events": current_events
            })
            
        responses = [
            {
                "response": {
                    "role": "model",
                    "parts": [{"text": final_text}]
                }
            }
        ]
        
        # Build the structured trace Case object
        graded_case = {
            "eval_case_id": case_id,
            "prompt": prompt_content,
            "responses": responses,
            "agent_data": {
                "agents": {
                    "expense_workflow": {
                        "agent_id": "expense_workflow",
                        "agent_type": "Workflow",
                        "instruction": "Ambient Expense Approval Graph Workflow"
                    }
                },
                "turns": turns
            }
        }
        graded_cases.append(graded_case)
        
    output_data = {"eval_cases": graded_cases}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully generated {len(graded_cases)} traces to {output_path}")


if __name__ == "__main__":
    main()
