import json
import time
from typing import List, Type, Literal

import openai
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from common.LLMPublisher import run_llm_pipeline
from common.llm import get_llm_response_pydantic2
from common.tokencouter import num_tokens_from_messages
from common.utilities import getDBRecord, execute_query_param, additional_context
import faulthandler

faulthandler.enable()


#

# def get_llm_response_pydantic2(apikey: str, baseurl: str, model: str, messages1: list,
#                                response_model: Type[BaseModel]) -> BaseModel | None:
#     client = OpenAI(
#         base_url=baseurl,
#         api_key=apikey,  # required, but unused
#     )
#     # Enable instructor patches for Groq client
#     retries = 0
#     max_retries = 15
#     max_tokens = 8192
#     temperature = 0.3
#     while retries < max_retries:
#         try:
#             # Assuming `client` is already set up for Groq API call
#             response = client.chat.completions.create(
#                 model=model,  # Adjust based on the model you want to use
#                 messages=messages1,
#                 response_format={"type": "json_object"},
#                 max_tokens=max_tokens,
#                 temperature=temperature
#
#             )
#
#             action = response_model(**json.loads(response.choices[0].message.content))
#             print("This is the Response by Agent ******\n",response.choices[0].message.content,"\n******")
#             return action  # ✅ Validation passed, return the object
#
#         except openai.BadRequestError as e:
#             print(f"BadRequestError encountered: {e}. Attempt {retries + 1}/{max_retries}")
#             # Log the error or inspect the response (e.g., response['error']) for further debugging
#         except OpenAIError as e:
#             print(f"OpenAIError encountered: {e}. Attempt {retries + 1}/{max_retries}")
#         except Exception as e:
#             print(f"Unexpected error: {e}. Attempt {retries + 1}/{max_retries}")
#
#         retries += 1
#         if retries < max_retries:
#             print(f"Retrying in {1} seconds...")
#             time.sleep(1)  # Wait for the specified delay before retrying
#         else:
#             print("Max retries reached. No valid response obtained.")
#     return None


class TestCase(BaseModel):
    testcase_summary: str
    test_steps: List[str]
    expected_result: str
    test_data: List[str]
    to_be_automated:bool
    priority:Literal["P1", "P2","P3"]
    tags: List[str]


class Requirement(BaseModel):
    requirement: str
    plan: str
    techniques: str
    testcases: List[TestCase]


class final_List(BaseModel):
    list: List[Requirement]


class Stepplan(BaseModel):
    activity: str
    tasks: List[str]


class Plan(BaseModel):
    plan: List[Stepplan]


def test_designer(userstrory_ref, config):
    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={userstrory_ref}"""
    storydetail = getDBRecord(user_story_detail, False)
    pr_id = storydetail['project_id']
    userstory = storydetail['detail']
    context_gathered=additional_context(userstrory_ref=userstrory_ref)

    # userstory = f"""
    # Acceptance Criteria:
    # Given I am a support user when the tenant has access to e-Learning lite then all users in the tenant should be given the Lite Permission (other roles should be hidden)
    # Given I am a support user if the tenant has e-Learning Advanced radio button on, then I can select other e-Learning permissions (course admin, assignment manager, regular user) and the lite permission will be hidden.
    # Given I am a support user if I turn the toggle off for e-Learning at the tenant level, all users should have their Lite Permission removed.
    # As a course admin, assignment manager or regular user with e-Learning advanced on, I should still be able to view the webcasts and watch them.
    # Given I am a Line Manager the description of the role should be updated to remove the / and swap it to a '
    #
    # As an e-Learning Lite user I need to be subscribed that permission so I can use e-Learning Lite
    # In scope:
    # When a tenant is created and e learning lite is on, all users for that tenant should be given the same permission called Lite Permission
    # The e -Learning Lite permission is the same permissions as a regular user. It will be displayed user the regular user permission.
    # The e-Learning Lite users only have this one permission, so we should disable or hide the other e-Learning permissions. Users of e-Learning lite will not be able to have course admins, assignment managers. Only if they are a paying e-Learning customer will they be able to select the roles (regular user, course admin, assignment manager)
    # Permission name: Lite User
    # Permission Description: Employees of the company who are not subscribed to the e-learning module, but have access to e-Learning Lite. This permission allows them to watch the ACA Webcasts within ComplianceAlpha.
    # If support turns of e-Learning lite for the tenant, then the permissions for all users in the tenant will be removed, and they can no longer see e-Learning lite.
    # Course admins, assignment managers and regular users for e-Learning advanced will still be able to view the webcasts and watch them without being assigned.
    # Additionally
    # Fix the typo on the line manager role. Should read: “Line Manager on the user’s profile” and not /
    #
    # Technical Details
    # Objective
    # The script adds a new Lite User role and associated permissions to specific clients in the LMS platform. It ensures proper permission management and grants access based on defined roles and features.
    # ________________________________________
    # Steps and Technical Details
    # 1.	Initialization
    # o	Identifiers, feature names, roles, and permission details are declared and initialized.
    # o	Parameters include:
    # 	@LMSProductKey, @LMSProductId: Identify the LMS Product.
    # 	Role and permission-specific parameters like @ElearningLightRoleId, @ElearningLiteUserPermissionId, etc.
    # 2.	Role Creation for ACA Group Clients
    # o	A new Lite User role (role_eLearning_lite_user) is created for ACA group clients.
    # o	If the role does not already exist, it is inserted into [Authorization].[Role].
    # 3.	Role Addition for Non-ACA Clients
    # o	The Lite User role is inserted for other clients based on specific conditions:
    # 	Clients must not belong to ACA.
    # 	The role must not already exist for the client.
    # 4.	Permission Management
    # o	A new permission (ELearningLiteUser) is added to [Authorization].[Permission] if it does not exist.
    # o	This permission is linked to the LMS module in [Authorization].[PermissionModule].
    # 5.	Grant Type Management
    # o	Grant types for permissions (e.g., View, Create, Update, Delete) are managed in [Authorization].[PermissionGrantType].
    # 6.	Permission-Feature Mapping
    # o	Permissions are mapped to LMS features (e-Learning Lite, e-Learning Advanced) in [Authorization].[PermissionProductFeature].
    # o	The mapping includes various grant types (View, Create, Update, Delete).
    # 7.	Role-Permission Mapping
    # o	The new Lite User role is linked to the ELearningLiteUser permission in [Authorization].[RolePermission].
    # 8.	Transaction Management
    # o	The script uses a TRY-CATCH block to ensure robust error handling.
    # o	Transactions are committed or rolled back based on the success or failure of the operations.
    #
    # Error Handling
    # •	Errors are captured in the CATCH block and logged with details like error number, procedure, message, and script reference (AGP-9953).
    # •	Any failed transactions are rolled back to maintain database integrity.
    # Key Tables Modified
    # •	[Authorization].[Role]
    # •	[Authorization].[Permission]
    # •	[Authorization].[PermissionModule]
    # •	[Authorization].[PermissionGrantType]
    # •	[Authorization].[PermissionProductFeature]
    # •	[Authorization].[RolePermission]
    # """

    # Task: Write a short poem about a cat
    task_description = userstory
    qna = []
    # Planning Phase
    # planning_prompt = f"""Create a step-by-step details plan in defined Valid JSON Object as follows:
    #  {{"plan": [{{"<Activity Name 1>":["<Task Name to perform>",""<Task Name to perform>""]}},{{"<Other Activity Name>":["<Task Name to perform>",""<Task Name to perform>""]}}}} to generate detailed test cases for {task_description}.
    #  Ensure that In the Generated JSON output does not have any incorrect mixed quotes are escaped properly. Ensure that  plan  covers UI validation if any specific mentioned in given task, boundary values, equivalence partitions, decision tables, state transitions, and use case scenarios to ensure 100% test coverage. Your response should be follow the provided JSON schema and escape any character like "  which may broke the JSON output with out any error and also Please do not add any opening and closing statements"""""
    planning_prompt = f"""You are an expert QA AI Agent specialized in advanced test design. Your goal is to generate a comprehensive test planning structure for the given task using systematic thinking and test design techniques. You must respond ONLY with a valid, well-escaped JSON object.

    Your task:

    1. Read and understand the input: {task_description}.
    2. Think through all functional and UI elements if any.
    3. Identify required validations and data types.
    4. Apply the following test design techniques as applicable:
       - Boundary Value Analysis (BVA)
       - Equivalence Partitioning (EP)
       - Decision Table Testing
       - State Transition Testing
       - Use Case Testing

    5. Construct a detailed plan to design the test cases to make sure all functionality get covered with high level scenario in this strict JSON format (output must NOT contain extra explanation or text) After completing your reasoning and Thinking:
   ### 🧹 Deduplication & Merging Rules

            To maintain clarity and avoid redundancy:

            - ❌ **Do not create features which is sharing the common test objective and result in creating duplicate test cases** when different techniques yield similar outcome or data sets.
            - ✅ **Merge features ** that cover the same objective, even if derived from different techniques and data sets.
            - 📌 **Each features contribute unique functionality coverage** (e.g., a new value range, rule, or flow).
            - 🧠 Use reasoning to **consolidate** and **annotate** features to reflect **combined coverage** where applicable.
            - ❌ **Do not create scenarios which objective is to test same functionality but different data sets becaue this may create duplicate test cases** when different techniques yield similar or overlapping data sets merege.
            - ✅ **Merge scenarios** that cover the same objective, even if derived from different techniques and data sets.
            - 📌 **Each scenarios must contribute unique test coverage** (e.g., a new value range, rule,flow or different data combinations).
            - 🧠 Use reasoning to **consolidate** and **annotate** scenarios to reflect **combined coverage** where applicable.

    **Instructions for Response:**
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

    **TASK**: {task_description}
    """""
    messages = [
        {"role": "system",
         "content": f"""You are an expert QA AI Agent specialized in advanced test design developed by Saksoft.You are well versed to read/understand and Create the JSON data as per given instructions"""},
        {"role": "user", "content": planning_prompt}
    ]
    print("Total tokens in Test planner:",
         num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
    plan = run_llm_pipeline(config, messages, Plan)
    # plan = get_llm_response_pydantic2(api_key,
    #                                   base_url, model, messages, Plan)
    print(
        f"&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&\nDesign Plan: {plan.model_dump_json()}\n&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")

    final_list_oftest_cases = []
    data2 = plan.model_dump_json()
    data2_dict = json.loads(data2)
    # data2_dict = plan
    for activity in data2_dict['plan']:
        # for activity['activity'], test_cases in activity.items():
        # print(f"\n{key}:")
        for task in activity['tasks']:

            # print(f"  - {test}")
            ### Insert Planing Items
            insert_query = """
                INSERT INTO `tcg`.`planning_item` (`project_id`, `story_id`, `description`)
                VALUES (%s, %s, %s);
            """

            description = f"{activity['activity']}:{task}"
            values = (pr_id, userstrory_ref, description)
            # insert_query = f"""INSERT INTO `tcg`.`planning_item`(`project_id`,`story_id`,`description`)
            #                                 VALUES
            #                                 ({pr_id},{userstrory_ref},"{activity['activity']}:{task}");"""
            planing_item_ID = execute_query_param(insert_query, values)
            print(planing_item_ID)
            action_prompt = f"""You are an expert-level QA test design AI agent. Your task is to generate high-quality test cases with 100% coverage using formal test design techniques from ISTQB standards. You will perform deep reasoning to extract all valid, invalid, boundary, workflow, and decision-based scenarios from the requirement.

            ---

            ### 🎯 Input Context

            - 📌 **Requirement Description**: {task_description}
            - 🛠️ **Action to be Performed**: {task}
            - 📘 **Test Design Technique Applied**: {activity['activity']}

            ---

            ### 🧠 Responsibilities

            1. Analyze the requirement deeply to identify:
               - Input fields and data ranges
               - Business logic, rules, decisions
               - States and transitions (if any)
               - User actions and flows
               - System validations and boundaries

            2. Apply the given test design technique to derive test cases:
               - **Boundary Value Analysis (BVA)**
               - **Equivalence Partitioning (EP)**
               - **Decision Table Testing**
               - **State Transition Diagrams (STD)**
               - **Use Case Testing**

            3. Ensure:
               - ✅ All valid and invalid partitions are covered
               - ✅ Boundaries and limits are tested
               - ✅ Every business rule or decision is represented
               - ✅ State transitions (if applicable) are exercised
               - ✅ End-to-end user flows are covered

            ---

            ### 🧹 Deduplication & Merging Rules

            To maintain clarity and avoid redundancy:

            - ❌ **DO NOT create duplicate test cases** when different techniques yield similar or overlapping data sets.
            - ✅ **Merge test cases** that cover the same objective or scenario, even if derived from different techniques.
            - 📌 **Each test case must add unique test coverage** (e.g., a new value range, rule, or flow).
            - 🧠 Use reasoning to **consolidate** and **annotate** test cases to reflect **combined coverage** where applicable.

            ---

            📦 ATTRIBUTE DEFINITIONS
            **priority** Only P1, P2, P3 possible values could be based below definations:
             - P1 (High): Core business flow, critical, compliance-driven, high failure risk
             - P2 (Medium): Frequently used but not business-blocking
             - P3 (Low): Informational, cosmetic, or rarely used features

            **to_be_automated**:
            Set to true if: 
             - The test is stable, repeatable, and frequently executed (e.g., login, API validation, calculation rules)
             - It has deterministic outcomes and adds value to regression suites
            Else, set to false (e.g., visual layout, one-time UX checks)

            🔐 Constraints
                - Do not include markdown, headers, or comments
                - Return only JSON output
                - Follow Pydantic model constraints exactly
                - Ensure each test case is unique, atomic, and covers a distinct rule/path/condition
                - Think systematically and logically before generating

            🔁 Think step-by-step before generating:
                - Identify inputs, outputs, and business conditions
                - Derive partitions, boundaries, decisions, or transitions based on the selected technique
                - Validate what is automatable and what isn’t
                - Based on give definition analyse the priority
                - Tag test cases for easy traceability and test planning

            ### 🧪 Coverage Guarantee Checklist (AI should implicitly reason through these)

                - ✅ Valid inputs
                - ✅ Invalid inputs
                - ✅ Edge boundaries
                - ✅ Decision combinations
                - ✅ State transitions
                - ✅ Workflow validations
                - ✅ Negative flows
                - ✅ Automation feasibility
                - ✅ Business risk-based prioritization

            ---
        **Instructions for Response:**
        ###IMPORTANT
        Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
            ```json
            {{
              "title": "Requirement",
              "type": "object",
              "required": ["requirement", "plan", "techniques", "testcases"],
              "properties": {{
                 "requirement": {{
                  "const": "{task}",
                  "description": "This field must match the expected requirement exactly."
                }},
                "plan": {{
                  "const": "{activity['activity']}",
                  "description": "Must exactly match the testing plan name used."
                }},
                "techniques": {{
                  "type": "string",
                  "description": "The name of the ISTQB technique applied (e.g., Boundary Value Analysis)."
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

            #
            messages = [
                {"role": "system",
                 "content": f"""You are an AI Test assistant developed by Saksoft to generate detailed test cases by Applying different ISTQB test designing technique.You are well versed to read/understand and Create the JSON data as per given instructions
                     #Use the following additional QnA context for user story gather during Story refinement sessions and 
                       ##DO NOT Miss any important and relevant points from given context like -conditions, key validations, Attribute Validation, Functional Flows and Error Validation Conditions.
                       ## Below is the Context:
                       ###{context_gathered}
                    
                    """},
                {"role": "user", "content": action_prompt}
            ]
            print("Total tokens in Test Creation:",
                  num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
            action = run_llm_pipeline(config, messages, Requirement)
            # action = get_llm_response_pydantic2(api_key,
            #                                     base_url, model, messages,
            #                                     Requirement)
            # print(f"Execution for step: {action2}\n")
            # action = Requirement(**json.loads(action2))
            try:
                for testcase in action.testcases:
                    testcase_summary = testcase.testcase_summary
                    test_steps = json.dumps(testcase.test_steps).encode('utf-8')  # Convert list to JSON array string
                    expected_result = testcase.expected_result
                    test_data = json.dumps(testcase.test_data).encode('utf-8')
                    tags = json.dumps(testcase.tags).encode('utf-8')  # Convert list to JSON array string
                    techniques = action.techniques
                    to_be_automated_db_value = int(testcase.to_be_automated)
                    priority = testcase.priority

                    # testcase_summary = testcase_summary.replace('"', '\\"')  # Escape double quotes in the summary
                    # expected_result = expected_result.replace('"', '\\"')  # Escape double quotes in the expected result
                    # test_steps = test_steps.replace('"', '\\"')  # Escape double quotes in the test_steps
                    # test_data = test_data.replace('"', '\\"')
                    # tags = tags.replace('"', '\\"')  # Esca
                    # Replace the hardcoded values in the insert query with your variables
                    insert_query = """
                            INSERT INTO `tcg`.`test_cases`
                            (`project_id`, `userstory_id`, `requirment_id`, `technique`, `summary`, `test_steps`, `expected_result`, `test_data`, `tags`,`priority`,`tobeautomate`)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s);
                        """

                    values = (
                        pr_id,
                        userstrory_ref,
                        planing_item_ID,
                        techniques,
                        testcase_summary,
                        test_steps,
                        expected_result,
                        test_data,
                        tags,
                        priority,
                        to_be_automated_db_value
                    )
                    # insert_query = f"""
                    #     INSERT INTO `tcg`.`test_cases` (`project_id`, `userstory_id`, `requirment_id`, `technique`, `summary`, `test_steps`, `expected_result`, `test_data`,`tags`)
                    #     VALUES ({pr_id}, {userstrory_ref}, {planing_item_ID}, "{techniques}", "{testcase_summary}", "{test_steps}", "{expected_result}", "{test_data}","{tags}");
                    # """
                    # Now execute your query (assuming execute_query_param is your function to run SQL queries)
                    test_case_id = execute_query_param(insert_query, values)
                    print(f"Test Cases Inserted :\n{test_case_id}\n")
            except Exception as e:
                print(f"""Test Cases are not returned BY AI due to Invalid Structure. Need to re try. Plan ID is: """,planing_item_ID)
            # print(f"Test Cases:\n{action}\n")
            ### Insert Test Cases
            final_list_oftest_cases.append(action)
    final_json = json.dumps([req.model_dump() for req in final_list_oftest_cases], indent=2)

    # Output the JSON
    # print(final_json)
    # records = []
    # for item in json.loads(final_json):
    #     requirement = item["requirement"]
    #     plan = item["plan"]
    #     techniques = item["techniques"]
    #
    #     for testcase in item["testcases"]:
    #         records.append({
    #             "Requirement": requirement,
    #             "Plan": plan,
    #             "Techniques": techniques,
    #             "Test Case Summary": testcase["testcase_summary"],
    #             "Test Steps": "\n".join(testcase["test_steps"]),
    #             "Expected Result": testcase["expected_result"],
    #             "Test Data": "\n".join(testcase["test_data"]),
    #             "Tags": ", ".join(testcase["tags"])
    #         })
    # # Convert to DataFrame
    # df = pd.DataFrame(records)
    #
    # # Save to Excel file
    # df.to_excel("testcases.xlsx", index=False, engine="openpyxl")
    #
    # print("Excel file 'testcases.xlsx' has been created successfully.")
    # print(f"Final Test Cases:\n{final_list_oftest_cases}\n")
