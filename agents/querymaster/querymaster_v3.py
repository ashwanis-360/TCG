import json
from typing import List, Optional

from fastapi import requests
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor

from common.LLMPublisher import run_llm_pipeline
from common.utilities import getDBRecord, execute_many


# ============================================================
# Pydantic Models
# ============================================================

class CoverageGap(BaseModel):
    """
    Represents a single identified gap in the user story.
    Not a question — a finding, like a static analysis report entry.
    """
    area: str = Field(
        description=(
            "Testing area: Workflow | Form Validation | UI/UX | "
            "Navigation | Authorization | Negative | Integration | Data"
        )
    )
    gap_title: str = Field(
        description="Short title of the gap, e.g. 'Missing error state for duplicate email'"
    )
    observation: str = Field(
        description=(
            "What is missing, ambiguous, or under-specified in the story. "
            "State this as a finding, not a question."
        )
    )
    risk: str = Field(
        description="What could go wrong in testing or production if this gap is not resolved."
    )
    assumption: str = Field(
        description=(
            "The ISTQB-grade assumption a QA engineer should use if this gap "
            "remains unresolved. Start with 'Assume that'."
        )
    )
    priority: str = Field(description="High | Medium | Low")
    confidence: float = Field(
        description=(
            "Confidence that this is a genuine gap (0.0 to 1.0). "
            "1.0 = definitively missing from story. "
            "0.5 = possibly implied but not stated."
        )
    )
    answerable_from_story: bool = Field(
        description=(
            "True if the story already answers this — meaning it is NOT a real gap. "
            "These entries will be filtered out before storage."
        )
    )


class StaticAnalysisReport(BaseModel):
    """Full static analysis output for a user story."""
    story_summary: str = Field(
        description="One sentence summary of what the story is asking the system to do."
    )
    coverage_gaps: List[CoverageGap]


class CritiqueResult(BaseModel):
    """Critic agent output — validates each gap before it is persisted."""
    gap_title: str
    verdict: str = Field(description="keep | rephrase | drop")
    revised_observation: Optional[str] = Field(
        default=None,
        description="Only populated when verdict is 'rephrase'."
    )
    reason: str


class CritiqueReport(BaseModel):
    critiques: List[CritiqueResult]


# ============================================================
# Specialist Category Groups
# Each group gets its own focused LLM call for higher precision
# ============================================================

CATEGORY_GROUPS = {
    "functional": {
        "areas": ["Workflow", "Form Validation", "Data"],
        "focus": (
            "Focus on business workflows, alternate flows, mandatory/optional fields, "
            "field format and length rules, error messages, data persistence, "
            "data consistency across systems, and data format validation."
        )
    },
    "ui_navigation": {
        "areas": ["UI/UX", "Navigation"],
        "focus": (
            "Focus on field visibility, conditional fields, layout rules, "
            "keyboard navigation, browser back/forward behaviour, "
            "direct URL access, and session handling across tabs."
        )
    },
    "security": {
        "areas": ["Authorization", "Negative"],
        "focus": (
            "Focus on role-based access control, permission restrictions, "
            "unauthorized access attempts, invalid token usage, "
            "manipulated requests, and invalid inputs."
        )
    },
    "integration": {
        "areas": ["Integration"],
        "focus": (
            "Focus on downstream system updates triggered by this story, "
            "API request/response contracts, data synchronization between systems, "
            "and integration failure handling."
        )
    }
}


# ============================================================
# Prompt Builder
# ============================================================

def _build_analysis_prompt(
    user_story: str,
    areas: List[str],
    focus_guidance: str,
    retrieved_context: str = ""
) -> str:
    """
    Builds a static analysis prompt grounded in retrieved context.
    Instructs the LLM to behave as an analyst producing findings,
    not a chatbot generating questions.
    """
    context_block = (
        f"""
## Known System Context (retrieved from knowledge base)
{retrieved_context}
"""
        if retrieved_context.strip()
        else "## Known System Context\nNot available for this story."
    )

    areas_str = ", ".join(areas)

    return f"""
You are a **Senior QA Architect** performing **Static Analysis** on a software requirement.

Static Analysis is a structured review technique from ISTQB that identifies defects,
ambiguities, and missing specifications in requirements — BEFORE test cases are written.

Your output is a **Coverage Gap Report**, not a Q&A list.
Each entry is a **finding** — a specific gap, ambiguity, or missing specification
that a QA engineer must resolve or make an assumption for.

---

## Scope for This Analysis Pass
Areas to cover: {areas_str}

{focus_guidance}

---

{context_block}

---

## User Story Under Analysis
{user_story}

---

## Static Analysis Rules

1. **Findings only** — Do not write questions. Write observations.
   BAD:  "What happens when the user submits an empty form?"
   GOOD: "Story does not specify system behaviour when mandatory fields are submitted empty."

2. Each finding must identify:
   - What is missing or ambiguous in the story
   - The risk it creates for testing or production
   - A practical ISTQB-grade assumption for QA engineers

3. Mark `answerable_from_story: true` if the story already covers this — the system
   will automatically filter those out.

4. Assign `confidence` honestly:
   - 1.0 = definitively absent from the story
   - 0.7 = implied but not explicitly stated
   - 0.5 = possibly covered by convention but not confirmed
   - Below 0.5 = borderline, include only if risk is High

5. Do NOT generate generic or obvious findings that apply to every system.
   Every finding must be **traceable to a specific element of this user story**.

6. Each area in scope must have at least 2 findings if applicable.

---

## Output Format

Return only valid JSON matching this schema:

{{
  "story_summary": "string",
  "coverage_gaps": [
    {{
      "area": "Workflow | Form Validation | UI/UX | Navigation | Authorization | Negative | Integration | Data",
      "gap_title": "string",
      "observation": "string",
      "risk": "string",
      "assumption": "string — must start with 'Assume that'",
      "priority": "High | Medium | Low",
      "confidence": 0.0,
      "answerable_from_story": false
    }}
  ]
}}

Do NOT include any text, explanation, or markdown outside the JSON.
"""


def _build_critic_prompt(
    user_story: str,
    gaps: List[dict]
) -> str:
    """
    Critic agent prompt. Reviews generated gaps and filters noise
    before anything gets persisted.
    """
    gaps_block = json.dumps(gaps, indent=2)

    return f"""
You are a **QA Review Lead** performing a quality gate on a Static Analysis Report.

Your task is to review each coverage gap identified by a junior QA architect
and decide whether it should be kept, rephrased, or dropped.

---

## User Story
{user_story}

---

## Coverage Gaps Under Review
{gaps_block}

---

## Review Criteria

For each gap, apply these rules:

**DROP if:**
- The story already answers this gap (answerable_from_story should have been true)
- The finding is too generic and applies to every system regardless of context
- The finding duplicates another entry
- The confidence is below 0.5 AND priority is Low or Medium

**REPHRASE if:**
- The observation is written as a question rather than a finding
- The gap_title is vague (e.g. "Missing info" — should be specific)
- The assumption is not ISTQB-grade (does not start with "Assume that", exceeds 50 words, or is trivial)

**KEEP if:**
- The finding is specific, traceable to the story, and testable
- The observation is a clear finding statement
- Risk and assumption are coherent

---

## Output Format

Return only valid JSON:

{{
  "critiques": [
    {{
      "gap_title": "string — must match original exactly",
      "verdict": "keep | rephrase | drop",
      "revised_observation": "string or null — only when verdict is rephrase",
      "reason": "string"
    }}
  ]
}}

Do NOT include any text outside the JSON.
"""


# ============================================================
# Vector DB Retrieval (stub — wire to your actual retriever)
# ============================================================

def _retrieve_context(user_story: str, pr_id: int,context_url,token) -> str:
    """
    Retrieves relevant context from the Vector Store via RAG API.

    Calls POST /query with the user story as the query and returns
    the cleaned context text ready for prompt injection.
    """

    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={user_story} and project_id={pr_id}"""
    storydetail = getDBRecord(user_story_detail, False)
    user_story = storydetail['detail']
    payload = {
        "query": user_story
    }

    # url = "http://127.0.0.1:8777/search"
    url = context_url
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response
    else:
        print("Search API return some error", response.status_code)





# ============================================================
# Core Analysis — Single Category Group
# ============================================================

def _analyse_category_group(
    config,
    user_story: str,
    group_name: str,
    group_config: dict,
    retrieved_context: str
) -> List[dict]:
    """
    Runs static analysis for one category group.
    Returns raw gap dicts (pre-critique).
    """
    prompt = _build_analysis_prompt(
        user_story=user_story,
        areas=group_config["areas"],
        focus_guidance=group_config["focus"],
        retrieved_context=retrieved_context
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a Senior QA Architect performing ISTQB static analysis. "
                "You produce structured coverage gap reports, not questions. "
                "Return only valid JSON — no markdown, no explanation."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    raw_result = run_llm_pipeline(config, messages, StaticAnalysisReport)

    if not raw_result or not isinstance(raw_result, StaticAnalysisReport):
        print(f"[{group_name}] LLM returned invalid or empty result — skipping group.")
        return []

    result: StaticAnalysisReport = raw_result

    # result: StaticAnalysisReport = run_llm_pipeline(config, messages, StaticAnalysisReport)

    # Filter out gaps the LLM itself flagged as answerable from story
    genuine_gaps = [
        g.model_dump()
        for g in result.coverage_gaps
        if not g.answerable_from_story
    ]

    print(f"[{group_name}] Raw gaps: {len(result.coverage_gaps)} | "
          f"Genuine: {len(genuine_gaps)}")

    return genuine_gaps


# ============================================================
# Critic Pass — Filter and Refine All Gaps
# ============================================================

def _critique_gaps(
    config,
    user_story: str,
    all_gaps: List[dict]
) -> List[dict]:
    """
    Runs the critic agent over all collected gaps.
    Returns only kept/rephrased gaps with any refinements applied.
    """
    if not all_gaps:
        return []

    prompt = _build_critic_prompt(user_story, all_gaps)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a QA Review Lead performing a quality gate. "
                "Be strict. Drop anything generic, duplicated, or already answered. "
                "Return only valid JSON — no markdown, no explanation."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    raw_critique = run_llm_pipeline(config, messages, CritiqueReport)

    if not raw_critique or not isinstance(raw_critique, CritiqueReport):
        print("[Critic] LLM returned invalid or empty result — keeping all gaps unreviewed.")
        return all_gaps

    critique: CritiqueReport = raw_critique
    # critique: CritiqueReport = run_llm_pipeline(config, messages, CritiqueReport)

    # Build lookup: gap_title → verdict + revision
    verdict_map = {c.gap_title: c for c in critique.critiques}

    refined = []
    for gap in all_gaps:
        title = gap["gap_title"]
        review = verdict_map.get(title)

        if review is None:
            # Critic did not review this gap — keep with a warning
            print(f"[Critic] Gap not reviewed: '{title}' — keeping by default")
            refined.append(gap)
            continue

        if review.verdict == "drop":
            print(f"[Critic] Dropped: '{title}' — {review.reason}")
            continue

        if review.verdict == "rephrase" and review.revised_observation:
            gap["observation"] = review.revised_observation
            print(f"[Critic] Rephrased: '{title}'")

        refined.append(gap)

    print(f"[Critic] {len(all_gaps)} gaps in → {len(refined)} gaps out")
    return refined


# ============================================================
# Deduplication
# ============================================================

def _deduplicate_gaps(gaps: List[dict]) -> List[dict]:
    """
    Simple title-based deduplication across category group outputs.
    In production, replace with semantic similarity deduplication
    using your vector DB.
    """
    seen = set()
    unique = []
    for gap in gaps:
        key = gap["gap_title"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(gap)
    return unique


# ============================================================
# Persist Gaps to DB
# ============================================================

def _persist_gaps(
    gaps: List[dict],
    pr_id: int,
    user_story_ref: int
) -> None:
    """
    Bulk inserts all refined gaps into tcg.static_analysis_gaps.
    Adjust table name and columns to match your schema.
    """
    if not gaps:
        print("[Persist] No gaps to store.")
        return

    records = [
        (
            pr_id,
            user_story_ref,
            g["area"],
            g["gap_title"],
            g["observation"],
            g["risk"],
            g["assumption"],
            g["priority"],
            g["confidence"]
        )
        for g in gaps
    ]

    execute_many(
        """
        INSERT INTO tcg.static_analysis_gaps
            (project_id, userstory_id, area, gap_title,
             observation, risk, assumption, priority, confidence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id, userstory_id, gap_title) DO UPDATE
            SET observation = EXCLUDED.observation,
                assumption  = EXCLUDED.assumption,
                confidence  = EXCLUDED.confidence
        """,
        records
    )

    print(f"[Persist] Stored {len(records)} gaps for story {user_story_ref}.")


# ============================================================
# Main Orchestrator
# ============================================================

def run_static_analysis(config, pr_id: int, user_story_ref: int,token,search_url,context_url) -> List[dict]:
    """
    Orchestrates the full static analysis pipeline for one user story.

    Flow:
        1. Fetch user story from DB
        2. Retrieve relevant context from vector DB (RAG)
        3. Run specialist LLM analysis per category group (parallel)
        4. Deduplicate across groups
        5. Run critic agent for quality gate
        6. Persist refined gaps to DB
        7. Return final gaps for downstream test case generation
    """

    # ── Step 1: Fetch User Story ──────────────────────────────
    story_row = getDBRecord(
        f"""
        SELECT project_id, detail
        FROM tcg.userstory
        WHERE _id = {user_story_ref}
        AND project_id = {pr_id}
        """,
        False
    )
    user_story: str = story_row["detail"]
    print(f"[Pipeline] Story loaded: {user_story_ref}")

    # ── Step 2: RAG Context Retrieval ─────────────────────────
    retrieved_context = _retrieve_context(user_story, pr_id,context_url,token)
    print(f"[Pipeline] Context retrieved: "
          f"{'yes' if retrieved_context.strip() else 'none available'}")

    # ── Step 3: Parallel Specialist Analysis ──────────────────
    all_gaps: List[dict] = []

    def analyse_group(group_name, group_config):
        return _analyse_category_group(
            config, user_story, group_name, group_config, retrieved_context
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(analyse_group, name, cfg): name
            for name, cfg in CATEGORY_GROUPS.items()
        }
        for future in futures:
            try:
                group_gaps = future.result()
                all_gaps.extend(group_gaps)
            except Exception as e:
                print(f"[Pipeline] Group '{futures[future]}' failed: {e}")

    print(f"[Pipeline] Total raw gaps collected: {len(all_gaps)}")

    # ── Step 4: Deduplication ─────────────────────────────────
    all_gaps = _deduplicate_gaps(all_gaps)
    print(f"[Pipeline] After deduplication: {len(all_gaps)}")

    # ── Step 5: Critic Quality Gate ───────────────────────────
    refined_gaps = _critique_gaps(config, user_story, all_gaps)

    # ── Step 6: Persist ───────────────────────────────────────
    _persist_gaps(refined_gaps, pr_id, user_story_ref)

    # ── Step 7: Return for downstream use ─────────────────────
    return refined_gaps
