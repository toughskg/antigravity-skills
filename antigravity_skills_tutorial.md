# The Agentic Command Line: Mastering Antigravity Skills

## 1. Introduction: The Evolution of Your Environment

The history of software development is a story of abstraction. We began by toggling hardware switches, moved to writing assembly, then entered the era of higher-level languages like C and Python. We evolved from managing memory manually to relying on garbage collectors.

Now, we are witnessing the next fundamental shift: **The Agentic Command Line**.

Traditional Command Line Interfaces (CLIs) are deterministic and rigid. You type `ls`, and you get a file list. You type `git commit -m "wip"`, and it commits exactly that text. These tools are powerful, but they don't *understand* your intent. They don't know that "fix the auth bug" implies checking `logs/`, reading `auth.py`, running `pytest`, and formatting the fix according to your team's style guide.

Antigravity brings a reasoner into your development loop. It interprets intent, plans workflows, and executes tasks on your behalf. But this power comes with a significant architectural challenge: **Context Saturation**.

### The Problem: Context Saturation
Modern AI models have massive context windows (1M+ tokens), but "dumping" your entire reality—every codebase interaction, every documentation PDF, every historical script—into the prompt at once is a flawed strategy.
1.  **Latency & Cost**: It makes every interaction slow and expensive. Processing 50 files for a simple "hello" concept is wasteful.
2.  **Needle-in-a-Haystack**: Finding the right linting rule in 100MB of unrelated text is statistically harder than finding it in a targeted 10KB instruction set.
3.  **Hallucination**: Overloading the model with irrelevant facts increases the chance it will apply the wrong rule to the wrong context.

### The Solution: Skills (Progressive Disclosure)
The industry has converged on a pattern known as **Skills**.
Instead of forcing the agent to "memorize" everything upfront, Skills allow you to package expertise—coding standards, migration scripts, templates, API usage patterns—into modular, on-demand units.

The agent only sees a "menu" of these skills (metadata names and descriptions). It loads the heavy instructions and resources **only when you ask for them**. This architecture is called **Progressive Disclosure**, and it is the key to a fast, powerful, and context-aware agent.

---

## 2. The Architecture of Agency

To build great skills, you must generally understand how Antigravity manages its "brain."

### 2.1 The Three Tiers of Context
1.  **Implicit Context (The Snapshot)**: The agent always possesses a high-level "spatial awareness". It knows the file tree structure, the current date, and your active file. It knows *where* it is without needing to read every byte.
2.  **Explicit Context (The Constitution)**: Rules defined in global files like `GEMINI.md` or `context.md` are *always* active. Use this tier for high-level invariants like "Always use TypeScript" or "Never use `sudo`." Do not put niche procedures here, or you will clutter the default context.
3.  **On-Demand Context (Skills)**: The dynamic layer. These live in specific folders. The agent scans their definitions at startup to build its capabilities index, but the actual content is only "installed" into the thought process when your intent matches their description.

### 2.2 Skills vs. MCP Tools
It is easy to confuse Skills with MCP (Model Context Protocol).
*   **MCP Tools are the Hands**: They are deterministic functions like `read_file`, `execute_query`, `search_web`, or `list_dir`. They *do* things.
*   **Skills are the Brains**: They are the *methodology* that tells the agent *how* and *when* to use those tools.

A "Database Migration *Skill*" (Methodology) might guide the agent to use the "Postgres *MCP Tool*" (Function) to run a specific SQL command. The Skill provides the *wisdom*; the Tool provides the *ability*.

---

## 3. Environment & Configuration

Skills live in specific directories. Antigravity respects a priority hierarchy:

1.  **Workspace Scope** (`.agent/skills/`):
    *   **Purpose**: Project-specific knowledge.
    *   **Usage**: Commit these to Git! This allows you to share "institutional knowledge" with your team. A new engineer can clone the repo and immediately have an agent that knows how to build, test, and deploy *that specific project*.
    
2.  **Global Scope** (`~/.gemini/antigravity/skills/`):
    *   **Purpose**: Personal workflows and preferences.
    *   **Usage**: Use this for things you want everywhere, like "Format JSON my way" or "Explain code like I'm 5".

---

## 4. Tutorial: Building Your Arsenal

We have generated 5 example skills in your `skills_tutorial/` directory. Each represents a "level up" in complexity and architectural pattern.

---

### Level 1: The Basic Router (`git-commit-formatter`)
*The "Hello World" of Skills*

**The Problem**:
Developers notoriously write lazy commit messages ("wip", "fix bug", "updates"). This makes git history useless. Enforcing "Conventional Commits" manually is tedious and often forgotten.

**The Solution**:
A pure prompt-engineering skill. By simply instructing the agent on the rules, we allow it to *act* as the enforcer.

**Anatomy**:
```text
git-commit-formatter/
└── SKILL.md  (Instructions only)
```

**The Code (`SKILL.md`)**:
We use the YAML frontmatter as the "router". The agent matches the `description` against user intent.
```yaml
---
name: git-commit-formatter
description: Formats git commit messages according to Conventional Commits specification.
---
```
The body contains the instructions, teaching the agent the allowed types:
> "Allowed Types: feat, fix, docs, style, refactor... Format: `<type>[optional scope]: <description>`"

**How to Run This Example**:
1.  Make a small change to any file in your workspace (e.g., add a comment to `demo_primes.py`).
2.  Open the chat and type: `Commit these changes.`.
3.  **Observation**: The Agent will not just run `git commit`. It will first "activate" the `git-commit-formatter` skill.
4.  **Result**: It will propose a message like `style(primes): add comment to GetPrimes function` instead of just `updated file`.

---

### Level 2: Asset Utilization (`license-header-adder`)
*The "Reference" Pattern*

**The Problem**:
Every source file in a corporate project might need a specific 20-line Apache 2.0 license header. Putting this static text directly into the prompt (or `SKILL.md`) is wasteful—it consumes tokens every time the skill is indexed, and the model might "hallucinate" typos in legal text.

**The Solution**:
Offloading the static text to a plain text file in a `resources/` folder. The skill instructs the agent to read this file *only* when needed.

**Anatomy**:
```text
license-header-adder/
├── SKILL.md
└── resources/
    └── HEADER_TEMPLATE.txt  (The heavy text)
```

**The Code**:
`SKILL.md` instruction:
> "First, read the content of the header template file located at `resources/HEADER_TEMPLATE.txt`. Prepend this exact text to the top of the file."

`resources/HEADER_TEMPLATE.txt`:
```text
/*
 * Copyright (c) 2024 Google LLC
 * Licensed under the Apache License, Version 2.0...
 */
```

**How to Run This Example**:
1.  Create a new dummy python file: `touch my_script.py`.
2.  Type: `Add the license header to my_script.py`.
3.  **Observation**: The agent will use the `view_file` tool to read `skills_tutorial/license-header-adder/resources/HEADER_TEMPLATE.txt`.
4.  **Result**: It will paste the content exactly, verbatim, into your file.

---

### Level 3: Learning by Example (`json-to-pydantic`)
*The "Few-Shot" Pattern*

**The Problem**:
Converting loose data (like a JSON API response) to strict code (like Pydantic models) involves dozens of micro-decisions. How should we name the classes? Should we use `Optional`? `snake_case` or `camelCase`? Writing out these 50 rules in English is tedious and error-prone.

**The Solution**:
**Few-Shot Prompting**. LLMs are pattern-matching engines. Showing them *one* "Golden Example" (Input -> Output) is often more effective than 500 words of instructions.

**Anatomy**:
```text
json-to-pydantic/
├── SKILL.md
└── examples/
    ├── input_data.json   (The Before State)
    └── output_model.py   (The After State)
```

**The Code**:
`SKILL.md` instruction:
> "Review the reference transformation in `examples/` to understand how to extract nested objects into classes and handle optional fields."

`examples/output_model.py`:
```python
class User(BaseModel):
    user_id: int
    preferences: Preferences  # Shows how to handle nesting
    last_login: Optional[str] # Shows how to handle nulls
```

**How to Run This Example**:
1.  Provide the agent with a snippet of JSON (paste it in chat or point to a file).
    ```json
    { "product": "Widget", "cost": 10.99, "stock": null }
    ```
2.  Type: `Convert this JSON to a Pydantic model`.
3.  **Observation**: The agent looks at the example pair in the skill folder.
4.  **Result**: It generates a Python class that perfectly mimics the coding style, imports, and structure of `output_model.py`, including handling the `null` stock as `Optional`.

---

### Level 4: Procedural Logic (`database-schema-validator`)
*The "Tool Use" Pattern*

**The Problem**:
LLMs are probabilistic. They are "vibes-based" engines. If you ask an LLM "Is this schema safe?", it might say "Yes" even if a critical `PRIMARY KEY` is missing, simply because the SQL *looks* correct. For strict engineering systems, 99% accuracy is 0% acceptable.

**The Solution**:
Delegating the check to a **Deterministic Script**. We use the Skill to *route* the agent to run a Python script that we wrote. The script provides binary (True/False) truth.

**Anatomy**:
```text
database-schema-validator/
├── SKILL.md
└── scripts/
    └── validate_schema.py  (The Validator)
```

**The Code**:
`scripts/validate_schema.py` (Standard Python):
```python
# Regex logic checking for 'id' and 'PRIMARY KEY'
if not re.search(r'\bid\b.*PRIMARY KEY', body):
    print("ERROR: Missing primary key 'id'")
    sys.exit(1)
```

`SKILL.md` instruction:
> "Do not read the file manually. Run `python scripts/validate_schema.py <file>` instead. If the exit code is 1, report the errors to the user."

**How to Run This Example**:
1.  Create a bad SQL file `bad_schema.sql`:
    ```sql
    CREATE TABLE users (name TEXT); 
    ```
2.  Type: `Validate bad_schema.sql`.
3.  **Observation**: The agent does *not* stare at the file and guess. It calls `run_command`.
4.  **Result**: The script fails (Exit Code 1). The agent reports: "The validation failed because the table 'users' is missing a primary key."

---

### Level 5: The Architect (`adk-tool-scaffold`)
*The "Batteries-Included" Pattern*

**The Problem**:
Complex tasks often require a sequence of operations that combine everything we've seen: creating files, following templates, and writing logic. Creating a new Tool for the ADK (Agent Development Kit) requires all of this.

**The Solution**:
**Composition**. We combine a **Script** (to handle the file creation/scaffolding), a **Template** (to handle boilerplate in `resources`), and an **Example** (to guide the logic generation).

**Anatomy**:
```text
adk-tool-scaffold/
├── SKILL.md
├── resources/
│   └── ToolTemplate.py.hbs (Jinja2 Template)
├── scripts/
│   └── scaffold_tool.py    (Generator Script)
└── examples/
    └── WeatherTool.py      (Reference Implementation)
```

**The Code**:
`SKILL.md` orchestrates the flow:
> "1. Run `scripts/scaffold_tool.py <Name>`. 2. Edit the file to add logic. 3. Refer to `examples/WeatherTool.py` for schema definition."

**How to Run This Example**:
1.  Type: `Create a new ADK tool called StockPrice to fetch data from an API`.
2.  **Step 1 (Scaffolding)**: The agent runs the python script. This instantly creates `StockPriceTool.py` with the correct class structure, imports, and class name `StockPriceTool`.
3.  **Step 2 (Implementation)**: The agent "reads" the file it just made. It sees `# TODO: Implement logic`.
4.  **Step 3 (Guidance)**: It's not sure how to define the JSON schema for the tool arguments. It checks `examples/WeatherTool.py`.
5.  **Completion**: It edits the file to add `requests.get(...)` and defines the `ticker` argument in the schema, exactly matching the ADK style.

---

## 5. Conclusion: Your New Superpower

This is not just a feature; it is a new operating system for your team's knowledge.

By encoding your practices into Skills, you turn your "Agentic Command Line" from a generic tool into a specialized member of your team. It doesn't just write code; it writes *your* code, follows *your* rules, and uses *your* tools.

You now have a `skills_tutorial/` folder in your workspace. Explore it. Modify the scripts. Break things. It is time to build your own superpowers.
