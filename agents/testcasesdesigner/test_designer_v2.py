# import json
# from typing import List, Literal
#
# from pydantic import BaseModel
#
# from common.LLMPublisher import run_llm_pipeline
# from common.tokencouter import num_tokens_from_messages
# from common.utilities import getDBRecord, execute_query_param, additional_context
#
# import faulthandler
# faulthandler.enable()
#
#
# # ------------------------------------------------
# # Pydantic Models (UNCHANGED)
# # ------------------------------------------------
#
# class TestCase(BaseModel):
#     testcase_summary: str
#     test_steps: List[str]
#     expected_result: str
#     test_data: List[str]
#     to_be_automated: bool
#     priority: Literal["P1", "P2", "P3"]
#     tags: List[str]
#
#
# class Requirement(BaseModel):
#     requirement: str
#     plan: str
#     techniques: str
#     testcases: List[TestCase]
#
#
# class Stepplan(BaseModel):
#     activity: str
#     tasks: List[str]
#
#
# class Plan(BaseModel):
#     plan: List[Stepplan]
#
#
# # ------------------------------------------------
# # Coverage Optimizer Agent
# # ------------------------------------------------
#
# def optimize_scenarios(requirement_json, config):
#
#     optimizer_prompt = f"""
# You are a senior QA architect responsible for optimizing generated test scenarios.
#
# Your objective is to refine the scenarios to ensure:
#
# 1. No duplicate scenarios
# 2. No overlapping scenarios
# 3. Full functional coverage
# 4. Practical number of scenarios
# 5. Each scenario contains complete test steps and test data
#
# Rules:
#
# • Merge scenarios testing same functionality
# • Remove redundant scenarios
# • Ensure coverage includes:
#   - happy path
#   - negative path
#   - edge cases
#   - boundary validation
#   - integration validation
#
# • Data permutations must stay inside test_data.
#
# • Final scenarios must be minimal but complete.
#
# * Output Instruction
# 1. Return optimized JSON using EXACT SAME schema strictly .
#
# Input scenarios:
# {json.dumps(requirement_json)}
#
# """
#
#     messages = [
#         {
#             "role": "system",
#             "content": "You are an advanced QA coverage optimization AI."
#         },
#         {
#             "role": "user",
#             "content": optimizer_prompt
#         }
#     ]
#
#     optimized = run_llm_pipeline(config, messages, Requirement)
#
#     return optimized
#
#
# # ------------------------------------------------
# # Duplicate Removal (fallback)
# # ------------------------------------------------
#
# def remove_duplicate_summaries(testcases):
#
#     seen = set()
#     unique = []
#
#     for tc in testcases:
#
#         key = tc.testcase_summary.lower().strip()
#
#         if key not in seen:
#             seen.add(key)
#             unique.append(tc)
#
#     return unique
#
#
# # ------------------------------------------------
# # Main Test Designer
# # ------------------------------------------------
#
# def test_designer(userstrory_ref, config):
#
#     user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={userstrory_ref}"""
#
#     storydetail = getDBRecord(user_story_detail, False)
#
#     pr_id = storydetail['project_id']
#     userstory = storydetail['detail']
#
#     context_gathered = additional_context(userstrory_ref=userstrory_ref)
#
#     task_description = userstory
#
#     # ------------------------------------------------
#     # Scenario Planning Agent
#     # ------------------------------------------------
#
#     planning_prompt = f"""
# You are a QA architect designing functional test scenarios.
#
# Goal:
# Create minimal yet complete functional scenarios.
#
# Rules:
#
# 1. Generate End-to-End functional scenarios.
# 2. Each scenario represents a workflow or validation area.
# 3. All the Functional Scenario should be Unique.
# 4. Keep scenarios between 6-8 ONLY.
# 5. Scenario must include:
#    - happy path
#    - negative validation
#    - edge conditions
#    - integration validation
# 6. Do NOT create activities for:
#    - security validation
#    - performance
#    - unless explicitly mentioned in the user story.
#
# Return JSON:
#
# {{
#  "plan":[
#    {{
#      "activity":"<Functional Area>",
#      "tasks":[
#        "<End to End Scenario>"
#      ]
#    }}
#  ]
# }}
#
# Requirement:
# {task_description}
# """
#
#     messages = [
#         {"role": "system",
#          "content": "You are a QA scenario planning AI."},
#         {"role": "user",
#          "content": planning_prompt}
#     ]
#
#     print("Planning Tokens:",
#           num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
#
#     plan = run_llm_pipeline(config, messages, Plan)
#
#     plan_dict = json.loads(plan.model_dump_json())
#
#     final_list_oftest_cases = []
#
#     # ------------------------------------------------
#     # Scenario Generator Agent
#     # ------------------------------------------------
#
#     for activity in plan_dict['plan']:
#
#         for task in activity['tasks']:
#
#             insert_query = """
#             INSERT INTO tcg.planning_item
#             (project_id,story_id,description)
#             VALUES (%s,%s,%s);
#             """
#
#             description = f"{activity['activity']}:{task}"
#
#             values = (pr_id, userstrory_ref, description)
#
#             planing_item_ID = execute_query_param(insert_query, values)
#
# #             scenario_prompt = f"""
# # Generate a complete End-to-End functional test scenario.
# #
# # Requirement:
# # {task_description}
# #
# # Scenario:
# # {task}
# #
# # Rules:
# #
# # • Include happy path
# # • Include negative validation
# # • Include boundary and edge cases
# # • Include integration verification
# # • Data permutations inside test_data
# # • Steps must be detailed and executable
# # CRITICAL OUTPUT FORMAT RULES:
# #
# # You MUST return JSON matching EXACTLY this structure.
# #
# # Top level fields REQUIRED:
# #
# # requirement
# # plan
# # techniques
# # testcases
# #
# # DO NOT return fields such as:
# #
# # testScenario
# # scenario_metadata
# # metadata
# # steps
# # test_data_permutations
# # scenarioId
# # scenario_metadata
# # exit_criteria
# #
# # If your reasoning produces scenario information,
# # you MUST map it into the following structure:
# #
# # testcase_summary = scenario title
# # test_steps = list of scenario steps
# # expected_result = final scenario validation
# # test_data = all data permutations
# # tags = scenario labels
# #
# # Only return JSON matching the schema.
# #
# # If any field is missing your answer will be rejected.
# # Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
# #             ```json
# #             {{
# #               "title": "Requirement",
# #               "type": "object",
# #               "required": ["requirement", "plan", "techniques", "testcases"],
# #               "properties": {{
# #                  "requirement": {{
# #                   "const": "{task}",
# #                   "description": "This field must match the expected requirement exactly."
# #                 }},
# #                 "plan": {{
# #                   "const": "{activity['activity']}",
# #                   "description": "Must exactly match the testing plan name used."
# #                 }},
# #                 "techniques": {{
# #                   "type": "string",
# #                   "description": "The name of the ISTQB technique applied (e.g., Boundary Value Analysis)."
# #                 }},
# #                 "testcases": {{
# #                   "type": "array",
# #                   "description": "List of detailed test cases",
# #                   "items": {{
# #                     "type": "object",
# #                     "required": [
# #                       "testcase_summary",
# #                       "test_steps",
# #                       "expected_result",
# #                       "test_data",
# #                       "to_be_automated",
# #                       "priority",
# #                       "tags"
# #                     ],
# #                     "properties": {{
# #                       "testcase_summary": {{
# #                         "type": "string",
# #                         "description": "Objective of the test case"
# #                       }},
# #                       "test_steps": {{
# #                         "type": "array",
# #                         "items": {{
# #                           "type": "string"
# #                         }},
# #                         "description": "Step-by-step execution instructions"
# #                       }},
# #                       "expected_result": {{
# #                         "type": "string",
# #                         "description": "Expected outcome after executing test steps"
# #                       }},
# #                       "test_data": {{
# #                         "type": "array",
# #                         "items": {{
# #                           "type": "string"
# #                         }},
# #                         "description": "Test input values used in the case"
# #                       }},
# #                       "to_be_automated": {{
# #                         "type": "boolean",
# #                         "description": "Indicates whether the test case should be automated"
# #                       }},
# #                       "priority": {{
# #                         "type": "string",
# #                         "enum": ["P1", "P2", "P3"],
# #                         "description": "Priority level of the test case"
# #                       }},
# #                       "tags": {{
# #                         "type": "array",
# #                         "items": {{
# #                           "type": "string"
# #                         }},
# #                         "description": "Classification tags like functional, UI, smoke, etc."
# #                       }}
# #                     }}
# #                   }}
# #                 }}
# #               }}
# #             }}
# #             ```
# # """
#             scenario_prompt = f"""
#             You are a senior QA engineer generating functional test scenarios.
#
#             Requirement:
#             {task_description}
#
#             Scenario to validate:
#             {task}
#
#             Testing activity:
#             {activity['activity']}
#
#             Instructions:
#
#             Generate practical functional test scenarios strictly based on the requirement.
#
#             Each test scenario must:
#
#             • Validate the described functionality
#             • Include happy path validation
#             • Include negative validation if applicable
#             • Include edge or boundary cases only if relevant
#             • Include integration validation if the requirement interacts with other components
#
#             Guidelines:
#
#             1. Do NOT invent new features.
#             2. Do NOT create unnecessary scenarios.
#             3. Keep the number of scenarios minimal.
#             4. All input combinations must be placed inside **test_data**, not as new testcases.
#             5. Steps must be executable and detailed.
#
#             **Instructions for Response:**
#         ###IMPORTANT
#         Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
#             ```json
#             {{
#               "title": "Requirement",
#               "type": "object",
#               "required": ["requirement", "plan", "techniques", "testcases"],
#               "properties": {{
#                  "requirement": {{
#                   "const": "{task}",
#                   "description": "This field must match the expected requirement exactly."
#                 }},
#                 "plan": {{
#                   "const": "{activity['activity']}",
#                   "description": "Must exactly match the testing plan name used."
#                 }},
#                 "techniques": {{
#                   "type": "string",
#                   "description": "The name of the ISTQB technique applied (e.g., Boundary Value Analysis)."
#                 }},
#                 "testcases": {{
#                   "type": "array",
#                   "description": "List of detailed test cases",
#                   "items": {{
#                     "type": "object",
#                     "required": [
#                       "testcase_summary",
#                       "test_steps",
#                       "expected_result",
#                       "test_data",
#                       "to_be_automated",
#                       "priority",
#                       "tags"
#                     ],
#                     "properties": {{
#                       "testcase_summary": {{
#                         "type": "string",
#                         "description": "Objective of the test case"
#                       }},
#                       "test_steps": {{
#                         "type": "array",
#                         "items": {{
#                           "type": "string"
#                         }},
#                         "description": "Step-by-step execution instructions"
#                       }},
#                       "expected_result": {{
#                         "type": "string",
#                         "description": "Expected outcome after executing test steps"
#                       }},
#                       "test_data": {{
#                         "type": "array",
#                         "items": {{
#                           "type": "string"
#                         }},
#                         "description": "Test input values used in the case"
#                       }},
#                       "to_be_automated": {{
#                         "type": "boolean",
#                         "description": "Indicates whether the test case should be automated"
#                       }},
#                       "priority": {{
#                         "type": "string",
#                         "enum": ["P1", "P2", "P3"],
#                         "description": "Priority level of the test case"
#                       }},
#                       "tags": {{
#                         "type": "array",
#                         "items": {{
#                           "type": "string"
#                         }},
#                         "description": "Classification tags like functional, UI, smoke, etc."
#                       }}
#                     }}
#                   }}
#                 }}
#               }}
#             }}
#             ```
#             ## IMPORTANT
#             - DO NOT include explanation or commentary in your output.
#             - DO NOT alter the structure or field names in the JSON.
#             - Ensure the output is valid JSON and can be parsed without error.
#             - Ensure the output is valid JSON and can be parsed without error.
#             - Do not include fields like "$schema", "title", "type", or "properties".
#             - You must only return a JSON **data object** that conforms to the expected structure — NOT a schema definition.
# The value of:
# requirement = "{task}"
# plan = "{activity['activity']}"
# .
#             """
#
#             messages = [
#                 {
#                     "role": "system",
#                     "content": f"""
# You are an enterprise QA scenario generator.
#
# Context from refinement:
# {context_gathered}
# """
#                 },
#                 {
#                     "role": "user",
#                     "content": scenario_prompt
#                 }
#             ]
#
#             #action = run_llm_pipeline(config, messages, Requirement)
#             raw_action = run_llm_pipeline(config, messages, dict)
#
#             normalized = normalize_llm_output(
#                 raw_action,
#                 task,
#                 activity['activity'],
#                 "Functional Scenario"
#             )
#
#             # action = Requirement(**normalized)
#             normalized = repair_testcases(normalized)
#
#             action = Requirement(**normalized)
#             # ------------------------------------------------
#             # Coverage Optimizer Agent (NEW)
#             # ------------------------------------------------
#
#             optimized_action = optimize_scenarios(
#                 action.model_dump(), config)
#
#             optimized_action.testcases = remove_duplicate_summaries(
#                 optimized_action.testcases)
#
#             # ------------------------------------------------
#             # Insert into DB
#             # ------------------------------------------------
#
#             for testcase in optimized_action.testcases:
#
#                 test_steps = json.dumps(testcase.test_steps).encode('utf-8')
#                 test_data = json.dumps(testcase.test_data).encode('utf-8')
#                 tags = json.dumps(testcase.tags).encode('utf-8')
#
#                 insert_query = """
#                 INSERT INTO tcg.test_cases
#                 (project_id,userstory_id,requirment_id,technique,
#                 summary,test_steps,expected_result,
#                 test_data,tags,priority,tobeautomate)
#                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
#                 """
#
#                 values = (
#                     pr_id,
#                     userstrory_ref,
#                     planing_item_ID,
#                     optimized_action.techniques,
#                     testcase.testcase_summary,
#                     test_steps,
#                     testcase.expected_result,
#                     test_data,
#                     tags,
#                     testcase.priority,
#                     int(testcase.to_be_automated)
#                 )
#
#                 test_case_id = execute_query_param(insert_query, values)
#
#                 print("Inserted TestCase:", test_case_id)
#
#             final_list_oftest_cases.append(optimized_action)
#
#     final_json = json.dumps(
#         [req.model_dump() for req in final_list_oftest_cases], indent=2)
#
#     return final_json
#
#
# def normalize_llm_output(data, requirement, plan, technique):
#
#     # Case 1: model returned correct format
#     if "testcases" in data:
#         return data
#
#     # Case 2: model returned scenario style
#     if "testScenario" in data:
#
#         scenario = data["testScenario"]
#
#         steps = []
#         for s in scenario.get("steps", []):
#             action = s.get("action", "")
#             expected = s.get("expectedResult", "")
#             steps.append(f"{action} | Expected: {expected}")
#
#         datasets = scenario.get("testData", {}).get("datasets", [])
#
#         test_data = []
#         for d in datasets:
#             test_data.append(json.dumps(d))
#
#         return {
#             "requirement": requirement,
#             "plan": plan,
#             "techniques": technique,
#             "testcases": [
#                 {
#                     "testcase_summary": scenario["metadata"]["title"],
#                     "test_steps": steps,
#                     "expected_result": "Scenario completed successfully",
#                     "test_data": test_data,
#                     "to_be_automated": True,
#                     "priority": "P1",
#                     "tags": scenario["metadata"].get("tags", [])
#                 }
#             ]
#         }
#
#     return data
#
#
# def repair_testcases(data):
#
#     if "testcases" not in data:
#         return data
#
#     for tc in data["testcases"]:
#
#         if "test_data" not in tc:
#             tc["test_data"] = ["N/A"]
#
#         if "to_be_automated" not in tc:
#             tc["to_be_automated"] = True
#
#         if "priority" not in tc:
#             tc["priority"] = "P2"
#
#         if "tags" not in tc:
#             tc["tags"] = ["functional"]
#
#         if "test_steps" not in tc:
#             tc["test_steps"] = ["Step details missing"]
#
#         if "expected_result" not in tc:
#             tc["expected_result"] = "Expected result not specified"
#
#     return data

import json
import re
from typing import List, Literal
from pydantic import BaseModel

from common.LLMPublisher import run_llm_pipeline
from common.utilities import getDBRecord, execute_query_param, additional_context

from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import DBSCAN

import faulthandler
faulthandler.enable()

# ------------------------------------------------
# MODELS
# ------------------------------------------------

class TestCase(BaseModel):
    testcase_summary: str
    test_steps: List[str]
    expected_result: str
    test_data: List[str]
    to_be_automated: bool
    priority: Literal["P1", "P2", "P3"]
    tags: List[str]


class Requirement(BaseModel):

    plan: str
    techniques: str
    testcases: List[TestCase]


class Stepplan(BaseModel):
    activity: str
    tasks: List[str]


class Plan(BaseModel):
    plan: List[Stepplan]


# ------------------------------------------------
# GLOBAL MODEL
# ------------------------------------------------

model = SentenceTransformer('all-MiniLM-L6-v2')


# ------------------------------------------------
# UTIL
# ------------------------------------------------

# def safe_encode(data):
#     if isinstance(data, str):
#         return data.encode("utf-8", "ignore").decode("utf-8")
#     return data

def safe_encode(data, replace_with=""):
    if not isinstance(data, str):
        return data

    # 1. Remove surrogate characters (ROOT CAUSE FIX)
    data = re.sub(r'[\ud800-\udfff]', replace_with, data)

    # 2. Normalize encoding (remove broken bytes)
    data = data.encode("utf-8", "ignore").decode("utf-8")

    # 3. Optional: remove emojis / non-ascii (recommended for QA data)
    data = re.sub(r'[^\x00-\x7F]+', replace_with, data)

    return data.strip()


def normalize_text(text):
    return " ".join(text.lower().strip().split())


# ------------------------------------------------
# EXACT DEDUP
# ------------------------------------------------

def remove_exact_duplicates(testcases):
    seen = set()
    unique = []

    for tc in testcases:
        key = normalize_text(tc.testcase_summary)
        if key not in seen:
            seen.add(key)
            unique.append(tc)

    return unique


# ------------------------------------------------
# SEMANTIC DEDUP
# ------------------------------------------------

def remove_semantic_duplicates(testcases, threshold=0.85):

    unique = []
    embeddings = []

    for tc in testcases:
        emb = model.encode(tc.testcase_summary)

        if not embeddings:
            unique.append(tc)
            embeddings.append(emb)
            continue

        sims = util.cos_sim(emb, embeddings)[0]

        if max(sims) < threshold:
            unique.append(tc)
            embeddings.append(emb)

    return unique


# ------------------------------------------------
# CLUSTERING
# ------------------------------------------------

def cluster_testcases(testcases):

    texts = [tc.testcase_summary for tc in testcases]
    embeddings = model.encode(texts)

    clustering = DBSCAN(eps=0.4, min_samples=1, metric='cosine')
    labels = clustering.fit_predict(embeddings)

    clusters = {}
    for label, tc in zip(labels, testcases):
        clusters.setdefault(label, []).append(tc)

    return clusters


def pick_representatives(clusters):
    return [cluster[0] for cluster in clusters.values()]


# ------------------------------------------------
# COVERAGE VALIDATION
# ------------------------------------------------

def validate_coverage(testcases):

    coverage = {
        "happy": False,
        "negative": False,
        "edge": False,
        "boundary": False,
        "integration": False
    }

    for tc in testcases:
        text = tc.testcase_summary.lower()

        if "valid" in text or "success" in text:
            coverage["happy"] = True

        if "invalid" in text or "error" in text:
            coverage["negative"] = True

        if "empty" in text or "null" in text:
            coverage["edge"] = True

        if "min" in text or "max" in text:
            coverage["boundary"] = True

        if "integration" in text or "api" in text or "failure" in text:
            coverage["integration"] = True

    return coverage


# ------------------------------------------------
# GLOBAL OPTIMIZER
# ------------------------------------------------

def classify_testcase(tc):

    text = tc.testcase_summary.lower()

    if "valid" in text or "success" in text:
        return "happy"

    if "invalid" in text or "error" in text:
        return "negative"

    if "min" in text or "max" in text or "length" in text:
        return "boundary"

    if "empty" in text or "null" in text or "whitespace" in text:
        return "edge"

    if "timeout" in text or "api" in text or "integration" in text:
        return "integration"

    return "other"

def smart_selection(testcases, max_per_category=3):

    buckets = {
        "happy": [],
        "negative": [],
        "boundary": [],
        "edge": [],
        "integration": [],
        "other": []
    }

    for tc in testcases:
        category = classify_testcase(tc)
        buckets[category].append(tc)

    final = []

    for cat, tcs in buckets.items():
        final.extend(tcs[:max_per_category])

    return final

def global_optimize(all_testcases):

    print(f"Before Optimization: {len(all_testcases)}")

    # Step 1: Exact dedup
    step1 = remove_exact_duplicates(all_testcases)

    # Step 2: Semantic dedup
    step2 = remove_semantic_duplicates(step1)

    print(f"After Dedup: {len(step2)}")

    # Step 3: Clustering (FIXED)
    clusters = cluster_testcases(step2)

    # 🔥 FIX: Only keep clusters with REAL grouping
    reduced = []
    for cluster in clusters.values():
        # pick BEST representative (longer description = richer test)
        best = sorted(cluster, key=lambda x: len(x.testcase_summary), reverse=True)[0]
        reduced.append(best)

    print(f"After Clustering: {len(reduced)}")

    # 🔥 FINAL CONTROL (MOST IMPORTANT)
    final = reduced
    # final = smart_selection(reduced, max_per_category=3)

    print(f"Final Optimized Count: {len(final)}")

    coverage = validate_coverage(final)

    print("Coverage:", coverage)

    return final, coverage
# ------------------------------------------------
# OUTPUT NORMALIZATION (UNCHANGED)
# ------------------------------------------------

def normalize_llm_output(data, plan, technique):

    if "testcases" in data:
        return data

    if "testScenario" in data:

        scenario = data["testScenario"]

        steps = []
        for s in scenario.get("steps", []):
            action = s.get("action", "")
            expected = s.get("expectedResult", "")
            steps.append(f"{action} | Expected: {expected}")

        datasets = scenario.get("testData", {}).get("datasets", [])

        test_data = [json.dumps(d) for d in datasets]

        return {
            "plan": plan,
            "techniques": technique,
            "testcases": [{
                "testcase_summary": scenario["metadata"]["title"],
                "test_steps": steps,
                "expected_result": "Scenario completed successfully",
                "test_data": test_data,
                "to_be_automated": True,
                "priority": "P1",
                "tags": scenario["metadata"].get("tags", [])
            }]
        }

    return data


def repair_testcases(data):

    if "testcases" not in data:
        return data

    for tc in data["testcases"]:
        tc.setdefault("test_data", ["N/A"])
        tc.setdefault("to_be_automated", True)
        tc.setdefault("priority", "P2")
        tc.setdefault("tags", ["functional"])
        tc.setdefault("test_steps", ["Step details missing"])
        tc.setdefault("expected_result", "Expected result not specified")

    return data


# ------------------------------------------------
# MAIN DESIGNER (UPDATED)
# ------------------------------------------------

def test_designer(userstrory_ref, config):

    # Fetch story
    query = f"""SELECT project_id,detail FROM tcg.userstory where _id={userstrory_ref}"""
    storydetail = getDBRecord(query, False)

    pr_id = storydetail['project_id']
    userstory = storydetail['detail']

    context = additional_context(userstrory_ref=userstrory_ref)

    # Planning
    planning_prompt = f"""
    You are an expert QA AI Agent specialized in advanced test design. Your goal is to generate a comprehensive test plan to get maximum coverage for the given task using systematic thinking and test design techniques. You must respond ONLY with a valid, well-escaped JSON object.

    Your task:

    1. Read and understand the input: {userstory}.
    2. Think through all functional and UI elements if any.
    3. Identify required validations and data types.
    4. Apply the following test design techniques as applicable:
       - Boundary Value Analysis (BVA)
       - Equivalence Partitioning (EP)
       - Decision Table Testing
       - State Transition Testing
       - Use Case Testing
Generate UNIQUE scenarios to have FULL Functional test coverage:
1. Happy
2. Invalid
3. Validation
4. Integration
5. Edge

Requirement:
{userstory}

###IMPORTANT
    Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
    ```json
    {{
      "title": "plan",
      "type": "object",
      "properties": {{
        "plan": {{
          "type": "array",
          "items": {{
            "type": "object",
            "title": "Stepplan",
            "properties": {{
              "activity": {{
                "type": "string",
                "description": "A short summary describing the feature to be included"
              }},
              "tasks": {{
                "type": "array",
                "items": {{
                  "type": "string",
                  "description": "A detailed Scenario description to be targeted for Test cases design"
                }},
                "minItems": 1,
                "description": "List of Scenario associated with the feature"
              }}
            }},
            "required": ["activity", "tasks"],
            "additionalProperties": false
          }},
          "minItems": 1,
          "description": "A sequence of step-by-step features with scenario to be included"
        }}
      }},
      "required": ["plan"],
      "additionalProperties": false
    }}
    ```
    Guidelines for JSON Output:
    - All quote characters (") must be correctly escaped.
    - Avoid mixing curly quotes (“ ”) or unescaped inner quotes.
    - Ensure the final output is a **fully parsable JSON** with no errors.
    - Do NOT include markdown, code blocks, opening/closing statements, or explanations.
    - Ensure the output is valid JSON and can be parsed without error.
    - Do not include fields like "$schema", "title", "type", or "properties".
    - You must only return a JSON **data object** that conforms to the expected structure — NOT a schema definition.

    Begin your analysis and return the JSON output based on the following task:
"""

    plan = run_llm_pipeline(config, [
        {"role": "system", "content": "Your a Experienced QA planner"},
        {"role": "user", "content": planning_prompt}
    ], Plan)

    plan_dict = json.loads(plan.model_dump_json())

    # GLOBAL COLLECTION
    all_testcases = []
    mapping = []

    for activity in plan_dict['plan']:
        # for task in activity['tasks']:

            desc = f"{activity['activity']}"

            req_id = execute_query_param(
                """INSERT INTO tcg.planning_item
                (project_id,story_id,description)
                VALUES (%s,%s,%s);""",
                (pr_id, userstrory_ref, desc)
            )

            scenario_prompt = f"""
Generate Maximum of 1-3 HIGH VALUE testcases only covering the given scenario.
#Scenario To cover: 
{activity['activity']}

#Your Test cases should have Included the coverage of below pointers as well, using any of- test_data, test_steps, or expected_result.NOTHING SHOULD BE MISSED:
{activity['tasks']}
The Purpose of these Test Cases is to test below User Story:
- {userstory }          
# Supporting Available Information:
    -{context} 

**Instructions for Response:**
        ###IMPORTANT
        Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
            ```json
            {{
              "title": "Requirement",
              "type": "object",
              "required": ["plan", "techniques", "testcases"],
              "properties": {{
                "plan": {{
                  "const": "{activity['activity']}",
                  "description": "Must exactly match the testing plan name used."
                }},
                "techniques": {{
                  "type": "string",
                  "description": "The name of the ISTQB technique applied (e.g., Boundary Value Analysis). Only One Values allowed"
                }},
                "testcases": {{
                  "type": "array",
                  "description": "List of detailed test cases",
                  "items": {{
                    "type": "object",
                    "required": [
                      "testcase_summary",
                      "test_steps",
                      "expected_result",
                      "test_data",
                      "to_be_automated",
                      "priority",
                      "tags"
                    ],
                    "properties": {{
                      "testcase_summary": {{
                        "type": "string",
                        "description": "Objective of the test case"
                      }},
                      "test_steps": {{
                        "type": "array",
                        "items": {{
                          "type": "string"
                        }},
                        "description": "Step-by-step execution instructions"
                      }},
                      "expected_result": {{
                        "type": "string",
                        "description": "Expected outcome after executing test steps"
                      }},
                      "test_data": {{
                        "type": "array",
                        "items": {{
                          "type": "string"
                        }},
                        "description": "Test input values used in the case"
                      }},
                      "to_be_automated": {{
                        "type": "boolean",
                        "description": "Indicates whether the test case should be automated"
                      }},
                      "priority": {{
                        "type": "string",
                        "enum": ["P1", "P2", "P3"],
                        "description": "Priority level of the test case"
                      }},
                      "tags": {{
                        "type": "array",
                        "items": {{
                          "type": "string"
                        }},
                        "description": "Classification tags like functional, UI, smoke, etc."
                      }}
                    }}
                  }}
                }}
              }}
            }}
            ```
            ## IMPORTANT
            - DO NOT include explanation or commentary in your output.
            - DO NOT alter the structure or field names in the JSON.
            - Ensure the output is valid JSON and can be parsed without error.
            - Ensure the output is valid JSON and can be parsed without error.
            - Do not include fields like "$schema", "title", "type", or "properties".
            - You must only return a JSON **data object** that conforms to the expected structure — NOT a schema definition.
            Begin now.
                
"""

            raw = run_llm_pipeline(config, [
                {"role": "system", "content": context},
                {"role": "user", "content": scenario_prompt}
            ], dict)

            normalized = normalize_llm_output(raw, activity['activity'], "Functional")
            normalized = repair_testcases(normalized)
            print("Normalized and Repaired Test Cases",normalized)

            action = Requirement(**normalized)
            print("Formated Test Cases", action)
            for tc in action.testcases:
                all_testcases.append(tc)
                mapping.append((tc, req_id))

    # --------------------------
    # GLOBAL OPTIMIZATION
    # --------------------------

    # final_testcases, coverage = global_optimize(all_testcases)
    final_testcases=all_testcases

    # --------------------------
    # FINAL INSERT ONLY
    # --------------------------

    for tc in final_testcases:

        req_id = next((m[1] for m in mapping if m[0] == tc), None)

        execute_query_param(
            """INSERT INTO tcg.test_cases
            (project_id,userstory_id,requirment_id,technique,
            summary,test_steps,expected_result,
            test_data,tags,priority,tobeautomate)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
            (
                pr_id,
                userstrory_ref,
                req_id,
                "Optimized",
                safe_encode(tc.testcase_summary),
                safe_encode(json.dumps(tc.test_steps)),
                safe_encode(tc.expected_result),
                safe_encode(json.dumps(tc.test_data)),
                safe_encode(json.dumps(tc.tags)),
                tc.priority,
                int(tc.to_be_automated)
            )
        )

    # return json.dumps({
    #     "total_before": len(all_testcases),
    #     "total_after": len(final_testcases)
    #
    # }, indent=2)