import time
from typing import List, Dict, Any, Type
import json

import openai
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from common.LLMPublisher import run_llm_pipeline_text, run_llm_pipeline
from common.llm import call_llm, get_llm_response_pydantic2
from common.tokencouter import num_tokens_from_messages
from common.utilities import execute_query_param


class UserStoryModel(BaseModel):
    prerequesites: List[str]
    summary: str
    actions: List[str]
    test_data: List[str]
    acceptance_criteria: List[str]


class AlluserStories(BaseModel):
    userstory: List[UserStoryModel]


class NMSProposal(BaseModel):
    executive_summary: str
    business_objectives: List[str]
    core_features: List[str]
    non_functional_requirements: List[str]


class features(BaseModel):
    core_feature: str
    approach: List[str]
    userstory: List[UserStoryModel]


class finalBRD(BaseModel):
    executive_summary: str
    business_objectives: List[str]
    feature_breackdown: List[features]


class approach_list(BaseModel):
    approach: List[str]


class BRDAutomationPipeline:
    def __init__(self, transcript: str, config, id: int):
        self.transcript = transcript
        self.relevant_content = ""
        self.brd = {}
        self.feature_set = []
        self.implementation_details = []
        self.user_stories = []
        self.id = id
        self.config = config

    def extract_relevant_content(self):
        prompt = f"Extract relevant content from the following meeting transcript:\n{self.transcript}\n"
        messages = [
            {"role": "system",
             "content": "You are good Listener on the call and efficiently extract all the relevant discussion points from transcript to define the further action items from these discussion"},
            {"role": "user", "content": prompt}
        ]
        self.relevant_content = run_llm_pipeline_text(self.config, messages)

        print("[✓] Relevant content extracted.",self.relevant_content)

    def generate_brd(self):
        prompt = (f"""Based on the relevant content: {self.relevant_content}, generate a Business Requirement Document (BRD).You response should strictly follow the below JSON Structure:"
                  {{
    "executive_summary": "Executive Summary of for whole software concepts",
    "business_objectives": [
        "Why and How This Software idea is important for overall Growth ", 
        "Better customer experience", "Sustainability goals",.. etc
    ],
    "core_features": [
        "Core Feature to be build to achieved the Desired business objective", ... etc
    ],
    "non_functional_requirements": [
        "Non Functional Aspect of this software for example Infra, Scalability, Usability, Security etc...",
    ]
}}
                  """
                  )
        messages = [
            {"role": "system",
             "content": "You are an Efficient AI Assistance as Business analyst which can create detailed Business Requirement Document (BRD) "},
            {"role": "user", "content": prompt}
        ]
        print("Total tokens in BA Role Proposal Extractor:",
              num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
        brd_response = run_llm_pipeline(self.config, messages, NMSProposal)
        self.brd = json.loads(brd_response.model_dump_json())
        print("[✓] BRD generated.",self.brd)

    def extract_features(self):
        self.feature_set = self.brd.get("core_features", [])
        print(f"[✓] Extracted {len(self.feature_set)} features from BRD.",self.feature_set)

    def elaborate_implementation(self):
        feature_breackdowndetails = []
        for i, feature in enumerate(self.feature_set, start=1):
            print(f"{i}. Feature: {feature}")
            prompt = f"""Generate implementation approach for these features: {feature}.Your response should strictly below pydentic model and generate JSON accordingly :
             ```python
                
               class approach(BaseModel):
                    approach:List[str]
            ```
            Do not include the open and closing statements or explanation conversation in you response"""

            messages = [
                {"role": "system",
                 "content": "You are an Efficient AI Assistance as Business analyst which can create detailed Business Requirement Document (BRD) "},
                {"role": "user", "content": prompt}
            ]
            print("Total tokens in BA Role Implementation Approach:",
                  num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
            impl_response = run_llm_pipeline(self.config, messages, approach_list)

            self.implementation_details = impl_response
            print("[✓] Implementation approach generated for features.", self.implementation_details)

            prompt = f"""Generate detailed user stories for this feature {feature} using following Implementation approach: {self.implementation_details}.Generate a user story in strictly Json formate according to that follows this Pydantic model:
                ```python
                
                class AlluserStories(BaseModel):
                    userstory:List[UserStoryModel]
                    ```
                    Where UserStoryModel is as below:
                ```python
                class UserStoryModel(BaseModel):
                    prerequesites: List[str]       # Any conditions or setup required before implementing the story
                    summary: str                   # One-line goal of the user story
                    actions: List[str]             # Steps user will take or system will perform
                    test_data: List[str]           # Sample input values or data required for validation
                    acceptance_criteria: List[str] # Clear and testable conditions for story completion
```
"""
            messages = [
                {"role": "system",
                 "content": "You An efficient business analyst and Create detailed user story with the all the details for given list of features Document (BRD) "},
                {"role": "user", "content": prompt}
            ]
            print("Total tokens in BA Role User Story Generator:",
                  num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
            user_story_response = run_llm_pipeline(self.config, messages,
                                                             AlluserStories)
            self.user_stories = user_story_response
            print("[✓] User stories generated.", self.user_stories)
            user_stories_json = [story.model_dump() for story in self.user_stories.userstory]
            # if isinstance(self.implementation_details, str):
            #     outputapproach_list = json.loads(self.implementation_details.approach.model_dump_json())
            # else:
            #     outputapproach_list = self.implementation_details
            detailedfeature = features(
                core_feature=feature,
                approach=self.implementation_details.approach,
                userstory=user_stories_json
            )
            feature_breackdowndetails.append(detailedfeature)
        finalbrd = finalBRD(
            executive_summary=self.brd.get("executive_summary"),
            business_objectives=self.brd.get("business_objectives", []),
            feature_breackdown=feature_breackdowndetails
        )
        print(finalbrd.model_dump_json())
        json_data = finalbrd.model_dump_json()
        data = json.loads(json_data)
        update_idea_query = """
            UPDATE tcg.intial_idea
            SET executive_summary = %s,
                business_objectives = %s
            WHERE id = %s
        """
        execute_query_param(update_idea_query, (
            data["executive_summary"],
            json.dumps(data["business_objectives"]),
            self.id
        ))

        # Step 2: Iterate through `feature_breackdown`
        for feature in data["feature_breackdown"]:
            insert_feature_query = """
                INSERT INTO feature_idea (description, approach, idea_id)
                VALUES (%s, %s, %s)
            """
            feature_id = execute_query_param(insert_feature_query, (
                feature["core_feature"],
                json.dumps(feature["approach"]),
                self.id
            ))

            # Step 3: Iterate through each `userstory` under this feature
            for story in feature["userstory"]:
                insert_user_story_query = """
                    INSERT INTO ideated_user_story
                    (prerequesites, summary, actions, test_data, acceptance_criteria, feature_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                execute_query_param(insert_user_story_query, (
                    json.dumps(story["prerequesites"]),
                    story["summary"],
                    json.dumps(story["actions"]),
                    json.dumps(story["test_data"]),
                    json.dumps(story["acceptance_criteria"]),
                    feature_id
                ))

        print("✅ Data inserted successfully.")
        update_status = """
                    UPDATE tcg.intial_idea
                    SET status = %s
                    WHERE id = %s
                """
        execute_query_param(update_status, (
            "Completed",
            self.id
        ))
        return finalbrd.model_dump_json()

    def run_pipeline(self):
        self.extract_relevant_content()
        self.generate_brd()
        self.extract_features()
        self.elaborate_implementation()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            "BRD": self.brd,
            "Implementation Details": self.implementation_details,
            "User Stories": self.user_stories
        }


# Example usage
# if __name__ == "__main__":
#     transcript_input = """
#     Duration: 30 Minutes
# Attendees:
# Rajiv (Lead Product Owner)
# Meera (Business Strategist)
# Ajay (Infra Architect)
# Nina (Product Owner - OSS)
# Saket (Tech Lead - Cloud & AI)
# Farah (CX Lead)
# [00:00] Rajiv:
# Thanks, everyone. Let’s jump in. The idea is to brainstorm a next-gen NMS platform – something truly AI-native, not just an upgraded version of legacy OSS.
# [00:02] Meera:
# Right. And we’re seeing serious operator pain points – managing hybrid networks, multi-vendor complexity, lack of visibility, and poor fault isolation. This could solve real business challenges.
# [00:04] Nina:
# Exactly. And I think the shift has to be from reactive fault management to predictive assurance. AIOps needs to be at the core, not an add-on.
# [00:06] Saket:
# We can integrate anomaly detection models, LLM-driven root cause analysis, and even closed-loop remediation. Think of it like: issues don’t just get detected—they get understood and resolved in real-time.
# [00:08] Rajiv:
# Let’s list down core capabilities. I’m noting:
# Predictive Fault Management
# Auto-Topology Discovery (for hybrid networks)
# AI-driven RCA and healing
# Unified View (Fiber, 5G, Satellite, etc.)
# Self-service analytics for NOC teams
# [00:11] Farah:
# Don’t forget experience monitoring. If this tool only serves network engineers, it’s a half-product. We should have a CX dashboard that correlates outages to customer churn risk.
# [00:13] Ajay:
# Infra-wise, we need to assume cloud-native from day zero. Kubernetes, microservices, real-time streaming with Kafka, and possibly a data lake for historical analysis.
# [00:15] Saket:
# Agreed. And for AIOps, we should bake in:
# Real-time telemetry ingestion
# ML pipelines (probably using Ray or Spark)
# LLM agents for RCA and knowledge retrieval from past incidents
# [00:18] Nina:
# Quick thought—can we modularize the system? Like, telcos can plug in just the parts they need? Fault Mgmt, Inventory, Performance, etc.
# [00:19] Rajiv:
# Yes, productization is key. We build the core intelligence platform, and expose capabilities via APIs and modular UIs. SaaS-style delivery model is what most Tier-2/3 telcos will prefer.
# [00:21] Meera:
# On the business side—how do we pitch this?
# Reduced OPEX by 30–40% via automation
# 50% faster MTTR
# Avoid SLA penalties
# Better NOC productivity
# Improved CX = lower churn
# [00:23] Farah:
# And sustainability! Energy-efficient ops, fewer truck rolls. Telcos are under pressure to show green impact.
# [00:24] Ajay:
# What about security? Multi-tenant SaaS will need strong tenant isolation. Role-based access, zero trust model, and encrypted event pipelines.
# [00:26] Rajiv:
# Great. Let’s assign action items:
# Saket: AI/ML architecture draft
# Ajay: Infra & deployment model
# Nina: Feature backlog (MVP & Phase 2)
# Meera: Business case and go-to-market outline
# [00:28] Meera:
# We should also validate with 2-3 existing telco clients. Quick interviews to fine-tune messaging.
# [00:29] Rajiv:
# Let’s plan a follow-up in a week. This is shaping up to be more than just a product—it’s a platform play.
# [00:30] [Meeting Ends]
#     """
#
#     pipeline = BRDAutomationPipeline(transcript=transcript_input)
#     pipeline.run_pipeline()
#     # outputs = pipeline.get_outputs()
#     #
#     # print("\n--- BRD ---")
#     # print(json.dumps(outputs["BRD"], indent=2))
#     #
#     # print("\n--- Implementation Details ---")
#     # print(json.dumps(outputs["Implementation Details"], indent=2))
#     #
#     # print("\n--- User Stories ---")
#     # print(json.dumps(outputs["User Stories"], indent=2))
