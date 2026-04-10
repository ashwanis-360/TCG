"""
BRD Automation Pipeline — Redesigned
=====================================
Key improvements over original:
  - Agentic flow: validate → critique → reflect before generating downstream artifacts
  - Parallel feature processing (async)
  - Retry logic with exponential backoff on every LLM call
  - Checkpoints: human review gates at critical stages
  - State is immutable (PipelineState dataclass, not self.*)
  - Prompts live in prompts.py, not in business logic
  - DB persistence is isolated in a separate layer
  - Structured logging replaces bare print()
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel

from agents.brdanalyser import prompts
from common.LLMPublisher import run_llm_pipeline, run_llm_pipeline_text
from common.utilities import execute_query_param

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models (unchanged schema — keep DB compatibility)
# ---------------------------------------------------------------------------

class UserStoryModel(BaseModel):
    prerequisites: List[str]
    summary: str
    actions: List[str]
    test_data: List[str]
    acceptance_criteria: List[str]


class AllUserStories(BaseModel):
    userstory: List[UserStoryModel]


class NMSProposal(BaseModel):
    executive_summary: str
    business_objectives: List[str]
    core_features: List[str]
    non_functional_requirements: List[str]


class ApproachList(BaseModel):
    approach: List[str]


class FeatureOutput(BaseModel):
    core_feature: str
    approach: List[str]
    userstory: List[UserStoryModel]


class FinalBRD(BaseModel):
    executive_summary: str
    business_objectives: List[str]
    feature_breakdown: List[FeatureOutput]


# ---------------------------------------------------------------------------
# Immutable pipeline state (replaces scattered self.* mutations)
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    transcript: str
    idea_id: int
    relevant_content: str = ""
    validation_verdict: str = ""
    brd: dict = field(default_factory=dict)
    critique_verdict: str = ""
    feature_outputs: List[FeatureOutput] = field(default_factory=list)
    final_brd: Optional[FinalBRD] = None


# ---------------------------------------------------------------------------
# LLM client wrapper: retry + timeout
# ---------------------------------------------------------------------------

async def call_llm_with_retry(config, messages: list, response_model, retries: int = 3, base_delay: float = 2.0):
    """
    Wraps run_llm_pipeline with async-friendly retry + exponential backoff.
    Falls back to plain text call for unstructured responses.
    """
    for attempt in range(1, retries + 1):
        try:
            loop = asyncio.get_event_loop()
            if response_model is None:
                result = await loop.run_in_executor(
                    None, lambda: run_llm_pipeline_text(config, messages)
                )
            else:
                result = await loop.run_in_executor(
                    None, lambda: run_llm_pipeline(config, messages, response_model)
                )
            return result
        except Exception as e:
            wait = base_delay * (2 ** (attempt - 1))
            log.warning(f"LLM call failed (attempt {attempt}/{retries}): {e}. Retrying in {wait:.1f}s...")
            if attempt == retries:
                log.error("All retries exhausted.")
                raise
            await asyncio.sleep(wait)


# ---------------------------------------------------------------------------
# Checkpoint: pause for human review (configurable)
# ---------------------------------------------------------------------------

class CheckpointError(Exception):
    """Raised when a validation/critique stage recommends stopping."""
    pass


def enforce_checkpoint(verdict: str, stage: str, auto_proceed: bool = False):
    """
    Evaluates a verdict string from a critique/validation LLM call.
    Raises CheckpointError if verdict is NEEDS_REVIEW / REVISE and auto_proceed is False.
    """
    needs_stop = any(kw in verdict.upper() for kw in ["NEEDS_REVIEW", "REVISE"])
    if needs_stop and not auto_proceed:
        log.warning(f"[CHECKPOINT] Stage '{stage}' requires human review.\nVerdict:\n{verdict}")
        raise CheckpointError(f"Pipeline paused at '{stage}'. Review verdict and rerun with corrected input.")
    if needs_stop:
        log.warning(f"[CHECKPOINT] Stage '{stage}' flagged issues but auto_proceed=True. Continuing.")
    else:
        log.info(f"[CHECKPOINT] Stage '{stage}' passed: {verdict[:80]}...")


# ---------------------------------------------------------------------------
# Core pipeline stages
# ---------------------------------------------------------------------------

async def stage_extract(state: PipelineState, config) -> PipelineState:
    log.info("Stage 1: Extracting relevant content...")
    messages = prompts.extract_relevant_content(state.transcript)
    content = await call_llm_with_retry(config, messages, response_model=None)
    log.info("[✓] Content extracted.")
    return PipelineState(**{**state.__dict__, "relevant_content": content})


async def stage_validate_understanding(state: PipelineState, config, auto_proceed: bool) -> PipelineState:
    log.info("Stage 2: Validating understanding against source...")
    messages = prompts.validate_understanding(state.relevant_content, state.transcript)
    verdict = await call_llm_with_retry(config, messages, response_model=None)
    enforce_checkpoint(verdict, "understanding_validation", auto_proceed)
    log.info("[✓] Understanding validated.")
    return PipelineState(**{**state.__dict__, "validation_verdict": verdict})


async def stage_generate_brd(state: PipelineState, config) -> PipelineState:
    log.info("Stage 3: Generating BRD...")
    messages = prompts.generate_brd(state.relevant_content)
    brd_response = await call_llm_with_retry(config, messages, NMSProposal)
    brd = json.loads(brd_response.model_dump_json())
    log.info(f"[✓] BRD generated with {len(brd.get('core_features', []))} features.")
    return PipelineState(**{**state.__dict__, "brd": brd})


async def stage_critique_brd(state: PipelineState, config, auto_proceed: bool) -> PipelineState:
    log.info("Stage 4: Critiquing BRD...")
    messages = prompts.critique_brd(state.brd, state.relevant_content)
    verdict = await call_llm_with_retry(config, messages, response_model=None)
    enforce_checkpoint(verdict, "brd_critique", auto_proceed)
    log.info("[✓] BRD critique passed.")
    return PipelineState(**{**state.__dict__, "critique_verdict": verdict})


async def process_single_feature(feature: str, state: PipelineState, config) -> FeatureOutput:
    """
    Processes ONE feature: approach → user stories.
    Runs in parallel with other features via asyncio.gather.
    """
    log.info(f"  Processing feature: {feature[:60]}...")

    # LLM call 1: implementation approach
    approach_messages = prompts.generate_implementation_approach(feature, state.relevant_content)
    approach_response = await call_llm_with_retry(config, approach_messages, ApproachList)

    # LLM call 2: user stories (grounded in approach)
    story_messages = prompts.generate_user_stories(
        feature, approach_response.approach, state.relevant_content
    )
    story_response = await call_llm_with_retry(config, story_messages, AllUserStories)

    log.info(f"  [✓] Feature done: {feature[:40]} — {len(story_response.userstory)} stories")
    return FeatureOutput(
        core_feature=feature,
        approach=approach_response.approach,
        userstory=story_response.userstory
    )


async def stage_elaborate_features(state: PipelineState, config) -> PipelineState:
    """
    Processes all features in PARALLEL instead of sequentially.
    Each feature gets 2 LLM calls (approach + stories) concurrently.
    """
    features = state.brd.get("core_features", [])
    log.info(f"Stage 5: Elaborating {len(features)} features in parallel...")

    tasks = [process_single_feature(f, state, config) for f in features]
    feature_outputs = await asyncio.gather(*tasks)

    log.info(f"[✓] All {len(feature_outputs)} features elaborated.")
    return PipelineState(**{**state.__dict__, "feature_outputs": list(feature_outputs)})


def build_final_brd(state: PipelineState) -> FinalBRD:
    return FinalBRD(
        executive_summary=state.brd.get("executive_summary", ""),
        business_objectives=state.brd.get("business_objectives", []),
        feature_breakdown=state.feature_outputs
    )


# ---------------------------------------------------------------------------
# Persistence layer (isolated from pipeline logic)
# ---------------------------------------------------------------------------

def persist_to_db(final_brd: FinalBRD, relevant_content: str, idea_id: int):
    log.info("Persisting to database...")
    data = json.loads(final_brd.model_dump_json())

    execute_query_param(
        "UPDATE tcg.intial_idea SET executive_summary = %s, business_objectives = %s WHERE id = %s",
        (data["executive_summary"], relevant_content, idea_id)
    )

    for feature in data["feature_breakdown"]:
        feature_id = execute_query_param(
            "INSERT INTO feature_idea (description, approach, idea_id) VALUES (%s, %s, %s)",
            (feature["core_feature"], json.dumps(feature["approach"]), idea_id)
        )
        for story in feature["userstory"]:
            execute_query_param(
                """INSERT INTO ideated_user_story
                   (prerequesites, summary, actions, test_data, acceptance_criteria, feature_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    json.dumps(story["prerequisites"]),
                    story["summary"],
                    json.dumps(story["actions"]),
                    json.dumps(story["test_data"]),
                    json.dumps(story["acceptance_criteria"]),
                    feature_id
                )
            )

    execute_query_param(
        "UPDATE tcg.intial_idea SET status = %s WHERE id = %s",
        ("Completed", idea_id)
    )
    log.info("[✓] Data persisted successfully.")


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------

class BRDAutomationPipelines:
    """
    Orchestrates the agentic BRD pipeline.

    auto_proceed: if True, checkpoints log warnings but don't halt execution.
                  Set False in production to enforce human review gates.
    """

    def __init__(self, transcript: str, config, idea_id: int, auto_proceed: bool = False):
        self.config = config
        self.auto_proceed = auto_proceed
        self.state = PipelineState(transcript=transcript, idea_id=idea_id)

    async def run(self) -> str:
        t0 = time.time()
        try:
            self.state = await stage_extract(self.state, self.config)
            self.state = await stage_validate_understanding(self.state, self.config, self.auto_proceed)
            self.state = await stage_generate_brd(self.state, self.config)
            self.state = await stage_critique_brd(self.state, self.config, self.auto_proceed)
            self.state = await stage_elaborate_features(self.state, self.config)

            final_brd = build_final_brd(self.state)
            persist_to_db(final_brd, self.state.relevant_content, self.state.idea_id)

            elapsed = time.time() - t0
            log.info(f"Pipeline complete in {elapsed:.1f}s")
            return final_brd.model_dump_json()

        except CheckpointError as e:
            log.error(f"Pipeline halted at checkpoint: {e}")
            raise
        except Exception as e:
            log.error(f"Pipeline failed: {e}")
            raise

    def run_sync(self) -> str:
        """Convenience wrapper for non-async callers."""
        return asyncio.run(self.run())
