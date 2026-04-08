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
    prerequisites: List[str]
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
        prompt = f"Analyze the given data from Business and technical point of view and Create anticipated user journey,exiting systems details (if available), Technical Details, Business Rules, Integrating Systems(Up stream or DownStream Systems) \n{self.transcript}\n"
        messages = [
            {"role": "system",
             "content": "You are Senior Business Analyst of Domain in Context and Can Define and Extract the Information's from Given Raw data to build the Software Systems"},
            {"role": "user", "content": prompt}
        ]
        self.relevant_content = run_llm_pipeline_text(self.config, messages)

        print("[✓] Relevant content extracted.",self.relevant_content)

    def generate_brd(self):
        prompt = (f"""Based on the content: {self.relevant_content}, generate a Business Requirement Document (BRD).You response should strictly follow the below JSON Structure:"
                  {{
    "executive_summary": "Executive Summary of for whole software concepts",
    "business_objectives": [
        "Why and How This Software idea is important for overall Growth ", 
        "Better customer experience", "Sustainability goals",.. etc
    ],
    "core_features": [
        "Core Feature to get Develop from the Product Owner point of view", ... etc
    ],
    "non_functional_requirements": [
        "Non Functional Aspect of this software for example Infra, Scalability, Usability, Security etc...",
    ]
}}

Also, Make sure the Sequence of Feature should be aligned as per Give User Journey and Related Technical Detailing along with the Integrating Systems
                  """
                  )
        messages = [
            {"role": "system",
             "content": "You are Senior Business analyst who can create detailed Business Requirement Document (BRD) "},
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
            Do not include the open and closing statements or explanation conversation in you response
            To make is accurate Please refer Below:
            {self.relevant_content}

"""

            messages = [
                {"role": "system",
                 "content": "You are A Senior Technical Architect who can plan the Details Design and Implementation Approach for a give Feature with Details"},
                {"role": "user", "content": prompt}
            ]
            print("Total tokens in BA Role Implementation Approach:",
                  num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
            impl_response = run_llm_pipeline(self.config, messages, approach_list)

            self.implementation_details = impl_response
            print("[✓] Implementation approach generated for features.", self.implementation_details)

            prompt = f"""Generate detailed user stories for this feature {feature} using following Implementation approach: {self.implementation_details}.Generate a user story in strictly Json formate according to that follows this Pydantic model:
                User Story should be relatable and Accurate as per given Context and it SHOULD NOT be Generic :{self.relevant_content}
                The User Story should be very much explainable for a Product Owner or Business User and not too much technical but should be the source of truth for the Developed and Testing Team
                ```python
                
                class AlluserStories(BaseModel):
                    userstory:List[UserStoryModel]
                    ```
                    Where UserStoryModel is as below:
                ```python
                class UserStoryModel(BaseModel):
                    prerequisites: List[str]       # Any conditions or setup required before implementing the story
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
                    json.dumps(story["prerequisites"]),
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
