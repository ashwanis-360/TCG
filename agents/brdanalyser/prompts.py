"""
Prompt Registry — all prompts live here, separate from business logic.
Each prompt is a function that returns a list of messages for the LLM.
"""

def extract_relevant_content(transcript: str) -> list:
    system = """You are a Senior Business Analyst with deep expertise in software product discovery.

Your job is to analyse raw input (meeting notes, transcripts, briefs) and extract structured understanding across five dimensions:
1. User Journey — who the users are, what they need, and the flow they follow
2. Existing Systems — current tools, legacy systems, pain points
3. Technical Context — APIs, data models, performance needs, constraints
4. Business Rules — logic, conditions, validations, compliance requirements
5. Integration Points — upstream and downstream systems, data flows, dependencies

Be specific and domain-aware. Do not hallucinate details not present in the input.
At the end, assign a confidence score (0-100) reflecting how complete the source material is."""

    user = f"""Analyse the following input and extract structured understanding across all five dimensions.

INPUT:
{transcript}

Format your response as:

## User Journey
[detail]

## Existing Systems
[detail]

## Technical Context
[detail]

## Business Rules
[detail]

## Integration Points
[detail]

## Confidence Score
[0-100] — [one sentence reason]"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate_understanding(relevant_content: str, transcript: str) -> list:
    system = """You are a critical reviewer of business analysis outputs.
Your job is to identify gaps, ambiguities, or assumptions in an extracted understanding document compared to the original source.
Be direct and precise. Do not be lenient."""

    user = f"""Compare the extracted understanding against the original source and identify:
1. Any key information present in the source but missing from the extraction
2. Any assumptions made that are not grounded in the source
3. Any ambiguous areas that need clarification before proceeding

ORIGINAL SOURCE:
{transcript}

EXTRACTED UNDERSTANDING:
{relevant_content}

Respond with:
## Gaps Found
[list each gap or "None found"]

## Ungrounded Assumptions
[list each or "None found"]

## Ambiguities
[list each or "None found"]

## Verdict
PROCEED or NEEDS_REVIEW — [one sentence reason]"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate_brd(relevant_content: str) -> list:
    system = """You are a Senior Business Analyst who writes precise Business Requirement Documents (BRDs).

Rules:
- Every feature must be traceable to the user journey or a business rule
- Features must be ordered by user journey sequence, not by technical complexity
- Non-functional requirements must be specific (e.g. "99.9% uptime SLA" not "the system should be reliable")
- Respond only with valid JSON matching the specified schema — no preamble, no markdown fences"""

    user = f"""Based on the following structured understanding, generate a BRD.

UNDERSTANDING:
{relevant_content}

Respond with this exact JSON structure:
{{
  "executive_summary": "2-3 sentence summary of the product concept and its value",
  "business_objectives": [
    "Specific, measurable objective — e.g. Reduce manual processing time by 40%"
  ],
  "core_features": [
    "Feature name: one-line description — ordered by user journey sequence"
  ],
  "non_functional_requirements": [
    "Category: specific requirement — e.g. Performance: API response < 200ms at p95"
  ]
}}"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def critique_brd(brd: dict, relevant_content: str) -> list:
    system = """You are a Product Owner reviewing a BRD draft before development begins.
You ask hard questions. You catch vague features, missing edge cases, and objectives that can't be measured."""

    user = f"""Review this BRD draft against the original understanding and identify weaknesses.

ORIGINAL UNDERSTANDING:
{relevant_content}

BRD DRAFT:
{brd}

Identify:
1. Features that are too vague to build from
2. Business objectives that cannot be measured
3. Missing features implied by the user journey
4. NFRs that are generic placeholders

Respond with:
## Weaknesses
[numbered list or "None found"]

## Missing Features
[list or "None found"]

## Verdict
APPROVED or REVISE — [reason]

## Revision Instructions
[only if REVISE — specific changes to make]"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate_implementation_approach(feature: str, relevant_content: str) -> list:
    system = """You are a Senior Technical Architect.
Your job is to define a concrete implementation approach for a given feature.

Rules:
- Each approach step must be actionable (a developer can act on it directly)
- Steps must reference the actual systems and integrations from the context
- Do not include generic steps like "write unit tests" or "deploy to cloud"
- Respond only with valid JSON — no preamble, no markdown fences"""

    user = f"""Generate a concrete implementation approach for this feature.

FEATURE:
{feature}

SYSTEM CONTEXT (use this to make the approach specific):
{relevant_content}

Respond with:
{{
  "approach": [
    "Step 1: specific, actionable implementation step referencing actual system components",
    "Step 2: ...",
    ...
  ]
}}"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate_user_stories(feature: str, approach: list, relevant_content: str) -> list:
    system = """You are an expert Business Analyst who writes user stories that are:
- Specific enough that a developer can implement without asking questions
- Testable enough that a QA engineer can write test cases without asking questions
- Written from the user's perspective, not the system's

BAD example (too generic):
  Summary: "User can log in"
  Acceptance criteria: "Login works correctly"

GOOD example (specific and testable):
  Summary: "Branch manager can authenticate using employee ID + OTP sent to registered mobile"
  Prerequisites: ["Employee record exists in HR system", "Mobile number verified"]
  Actions: ["Enter 6-digit employee ID", "Request OTP", "Enter OTP within 5-minute window"]
  Test data: ["Valid ID: EMP001", "Invalid ID: EMP999", "Expired OTP: wait 6 mins"]
  Acceptance criteria: [
    "OTP expires after 5 minutes",
    "3 failed OTP attempts lock the account for 30 minutes",
    "Successful login redirects to role-specific dashboard"
  ]

Respond only with valid JSON — no preamble, no markdown fences."""

    user = f"""Generate detailed, domain-specific user stories for this feature.

FEATURE:
{feature}

IMPLEMENTATION APPROACH:
{approach}

DOMAIN CONTEXT (make stories specific to this domain — no generic placeholders):
{relevant_content}

Respond with:
{{
  "userstory": [
    {{
      "prerequisites": ["condition that must be true before this story begins"],
      "summary": "As a [specific role], I can [specific action] so that [specific outcome]",
      "actions": ["Step 1 the user takes", "Step 2", ...],
      "test_data": ["Specific value or scenario to test with"],
      "acceptance_criteria": ["Specific, testable condition for completion"]
    }}
  ]
}}"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
