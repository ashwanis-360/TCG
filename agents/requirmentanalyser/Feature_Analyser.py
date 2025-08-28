import time
from typing import List, Type, Literal, Union

import openai
import json
from pydantic import BaseModel
from openai import OpenAI, OpenAIError

from common.LLMPublisher import run_llm_pipeline
from common.llm import get_llm_response_pydantic2
from common.tokencouter import num_tokens_from_messages
from common.utilities import getDBRecord, execute_query_param


class Requirement(BaseModel):
    requirement_detail: str
    type: Literal["Functional", "Non-functional"]
    testdata: List[str]
    stepstotest: List[str]
    is_ask: bool


class RequirementsContainer(BaseModel):
    requirements: List[Requirement]


class AttributeDetail(BaseModel):
    attribute_name: str
    techniquedetails: List[Union[str, int]]


class Technique(BaseModel):
    applicable: bool
    attributes: List[AttributeDetail]


class TestDesignTechniques(BaseModel):
    boundary_value_analysis: Technique
    equivalent_class_partitioning: Technique
    state_transition_diagram: Technique
    decision_table: Technique
    use_case_testing: Technique


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
#             )
#             print("This is the Response by Agent ******\n", response.choices[0].message.content, "\n******")
#             action = response_model(**json.loads(response.choices[0].message.content))
#             return action  # If the response is successful, return it
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


def requirment_spliter(config, userstrory_ref):
    ## Reading Questions And Answer and Storing into QNA
    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={userstrory_ref}"""
    storydetail = getDBRecord(user_story_detail, False)
    pr_id = storydetail['project_id']
    userstory = storydetail['detail']
    requirment_split_prompt = f"""You are an AI Tester developed by Saksoft which can plan the test execution by 
            breaking the the whole User story in modular functions to tested as a single unit.

        ## Task Objective:
        Split the given user story into a set of key features under the categories:
          1. Functional
          2. Non-Functional

        For **Non-Functional**, include the following sub-categories if applicable:
          - Performance aspects
          - Security and VAPT aspects
          - Compliance aspects (e.g., Data Privacy, HIPAA if it's a healthcare system)

        ---

       ## Definitions for Each Requirement:
    - `requirement_detail` (string): Mandatory. A short description of what the feature does.
    - `type` (string): Must be one of ["Functional", "Non-functional"].
    - `testdata` (array of strings): List of input data attribute names needed to test this feature. Use an empty list (`[]`) if none required.
    - `stepstotest` (array of strings): Mandatory. Each string should represent a high-level step to test the feature.
    - `is_ask` (boolean): Mandatory. Rules:
        - All Functional features → `true`
        - For Non-functional:
            - If explicitly mentioned in the story → `true`
            - If suggested by you as a best practice → `false`
        ---

        ## Input User Story:
        {userstory}

        ---

        ## Output Instructions:
        1. Only respond with a JSON in the format shown below.
        2. Do NOT include any additional explanation or text.
        3. Strictly follow this JSON schema:

        ⚠️ If ANY key is misspelled (like `stepstot,est`), the system will REJECT your output and rerun you.

    DO NOT:
    - Misspell field names
    - Change the field order
    - Omit any required field
    - 

    **Instructions for Response:**
    ###IMPORTANT
    Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
        ```json
        {{
          "title": "RequirementsContainer",
          "type": "object",
          "properties": {{
            "requirements": {{
              "type": "array",
              "items": {{
                "type": "object",
                "title": "Requirement",
                "properties": {{
                  "requirement_detail": {{
                    "type": "string",
                    "minLength": 1
                  }},
                  "type": {{
                    "type": "string",
                    "enum": ["Functional", "Non-functional"]
                  }},
                  "testdata": {{
                    "type": "array",
                    "items": {{
                      "type": "string"
                    }}
                  }},
                  "stepstotest": {{
                    "type": "array",
                    "items": {{
                      "type": "string"
                    }},
                    "minItems": 1
                  }},
                  "is_ask": {{
                    "type": "boolean"
                  }}
                }},
                "required": [
                  "requirement_detail",
                  "type",
                  "testdata",
                  "stepstotest",
                  "is_ask"
                ],
                "additionalProperties": false
              }},
              "minItems": 1
            }}
          }},
          "required": ["requirements"],
          "additionalProperties": false
        }}
        ```
        ## INSTRUCTIONS:
- DO NOT include explanation or commentary in your output.
- DO NOT alter the structure or field names in the JSON.
- Ensure the output is valid JSON and can be parsed without error.
- Do not include fields like "$schema", "title", "type", or "properties".
- You must only return a JSON **data object** that conforms to the expected structure — NOT a schema definition.

        """
    messages = [
        {"role": "system",
         "content": "You are an AI Tester Agent developed by Saksoft who Analyse and  split the bigger user story scope in smaller modules to make test execution easy.You are efficient to read/understand and Create the JSON data as per given instructions"},
        {"role": "user", "content": requirment_split_prompt}
    ]
    print("Total tokens in user Feature Extraction planning:", num_tokens_from_messages(messages, model="gpt-3.5-turbo"))

    features = run_llm_pipeline(config, messages, RequirementsContainer)
    # features = get_llm_response_pydantic2(apikey,
    #                                       baseurl, model, messages, RequirementsContainer)
    print("*********************", features.model_dump_json(), "************************")
    for req in features.requirements:
        try:
            query = """
                    INSERT INTO `tcg`.`requirments`
                        (`project_id`, `userstory_id`, `detail`, `type`, `data`, `test_steps`)
                    VALUES
                        (%s, %s, %s, %s, %s, %s);
                """
            params = (
                pr_id,
                userstrory_ref,
                req.requirement_detail,
                req.type,
                json.dumps(req.testdata),
                json.dumps(req.stepstotest)
            )
            requirement_id=execute_query_param(query, params)

            requirment_analyser(config, req,userstory,requirement_id)
        except Exception as e:

            print("*************",e," *************")



def requirment_analyser(config, req: BaseModel, userstory,id):


        ## Reading Questions And Answer and Storing into QNA

        requirment_analyzer = f"""You are an intelligent QA Analyst Agent with expertise in analyzing software features and mapping them to the correct test case design techniques. Your goal is to evaluate the given feature, analyze its applicability against five specific test design techniques, and output your reasoning in a structured JSON format.

        ## INPUT CONTEXT:
        - Feature Description: {req.requirement_detail}
        - Defined Test Data: {req.testdata}
        - Defined Test Steps: {req.stepstotest}
        - User Story: {userstory}

        ## ANALYSIS OBJECTIVE:
        You must analyze the above feature and determine, for each of the following Test Design Techniques, whether it is applicable and, if so, what data or attributes make it eligible:

        1. Boundary Value Analysis (BVA)
        2. Equivalent Class Partitioning (ECP)
        3. State Transition Diagram (STD)
        4. Decision Table
        5. Use Case Testing

        ## ANALYSIS RULES:

        ### 1. Boundary Value Analysis (BVA):
        - Applicable when input fields involve numeric/range-based values.
        - Identify attributes with defined boundaries (min, max, just inside, just outside).

        ### 2. Equivalent Class Partitioning (ECP):
        - Applicable when inputs can be categorized into valid/invalid classes.
        - Identify groupings based on formats, types, categories, etc.

        ### 3. State Transition Diagram (STD):
        - Applicable when system behavior changes based on a current state or status.
        - Look for workflows, sequences, or state-based transitions.

        ### 4. Decision Table:
        - Applicable when there are multiple logical conditions resulting in specific outcomes.
        - Extract combinations of conditions and their corresponding results.

        ### 5. Use Case Testing:
        - Applicable when the user story involves business flows or role-based actions.
        - Identify steps, actors, and goals derived from the story.

        ## DEDUPLICATION RULE:
        🔴 IMPORTANT: **If an attribute and its values are already listed under one test design technique, DO NOT repeat it under another.**  
        Include each attribute **only once** under the most relevant applicable technique to avoid duplication.

       **Instructions for Response:**
        ###IMPORTANT
       Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
        ```json
        {{
          "title": "TestDesignTechniques",
          "type": "object",
          "description": "Schema for capturing applicability of various test design techniques",
          "minProperties": 1,
          "maxProperties": 5,
          "properties": {{
            "boundary_value_analysis": {{
              "type": "object",
              "required": ["applicable", "attributes"],
              "properties": {{
                "applicable": {{
                  "type": "boolean",
                  "description": "Indicates whether Boundary Value Analysis is applicable"
                }},
                "attributes": {{
                  "type": "array",
                  "description": "List of relevant attributes for Boundary Value Analysis",
                  "items": {{
                    "type": "object",
                    "required": ["attribute_name", "techniquedetails"],
                    "properties": {{
                      "attribute_name": {{
                        "type": "string",
                        "description": "Name of the input attribute"
                      }},
                      "techniquedetails": {{
                        "type": "array",
                        "minItems": 1,
                        "description": "List of boundary values to test",
                        "items": {{
                          "oneOf": [
                            {{ "type": "string" }},
                            {{ "type": "integer" }}
                          ]
                        }}
                      }}
                    }},
                    "additionalProperties": false
                  }}
                }}
              }},
              "additionalProperties": false
            }},
            "equivalent_class_partitioning": {{
              "type": "object",
              "required": ["applicable", "attributes"],
              "properties": {{
                "applicable": {{
                  "type": "boolean",
                  "description": "Indicates whether Equivalence Class Partitioning is applicable"
                }},
                "attributes": {{
                  "type": "array",
                  "description": "List of relevant attributes for ECP",
                  "items": {{
                    "type": "object",
                    "required": ["attribute_name", "techniquedetails"],
                    "properties": {{
                      "attribute_name": {{
                        "type": "string",
                        "description": "Name of the input attribute"
                      }},
                      "techniquedetails": {{
                        "type": "array",
                        "minItems": 1,
                        "description": "List of equivalence class values",
                        "items": {{
                          "oneOf": [
                            {{ "type": "string" }},
                            {{ "type": "integer" }}
                          ]
                        }}
                      }}
                    }},
                    "additionalProperties": false
                  }}
                }}
              }},
              "additionalProperties": false
            }},
            "state_transition_diagram": {{
              "type": "object",
              "required": ["applicable", "attributes"],
              "properties": {{
                "applicable": {{
                  "type": "boolean",
                  "description": "Indicates whether State Transition Diagram is applicable"
                }},
                "attributes": {{
                  "type": "array",
                  "description": "List of state-dependent inputs",
                  "items": {{
                    "type": "object",
                    "required": ["attribute_name", "techniquedetails"],
                    "properties": {{
                      "attribute_name": {{
                        "type": "string",
                        "description": "Name of the input attribute"
                      }},
                      "techniquedetails": {{
                        "type": "array",
                        "minItems": 1,
                        "description": "List of possible states or transitions",
                        "items": {{
                          "oneOf": [
                            {{ "type": "string" }},
                            {{ "type": "integer" }}
                          ]
                        }}
                      }}
                    }},
                    "additionalProperties": false
                  }}
                }}
              }},
              "additionalProperties": false
            }},
            "decision_table": {{
              "type": "object",
              "required": ["applicable", "attributes"],
              "properties": {{
                "applicable": {{
                  "type": "boolean",
                  "description": "Indicates whether Decision Table testing is applicable"
                }},
                "attributes": {{
                  "type": "array",
                  "description": "List of attributes used in decision-making logic",
                  "items": {{
                    "type": "object",
                    "required": ["attribute_name", "techniquedetails"],
                    "properties": {{
                      "attribute_name": {{
                        "type": "string",
                        "description": "Name of the input attribute"
                      }},
                      "techniquedetails": {{
                        "type": "array",
                        "minItems": 1,
                        "description": "List of combinations of input conditions",
                        "items": {{
                          "oneOf": [
                            {{"type": "string" }},
                            {{ "type": "integer" }}
                          ]
                        }}
                      }}
                    }},
                    "additionalProperties": false
                  }}
                }}
              }},
              "additionalProperties": false
            }},
            "use_case_testing": {{
              "type": "object",
              "required": ["applicable", "attributes"],
              "properties": {{
                "applicable": {{
                  "type": "boolean",
                  "description": "Indicates whether Use Case Testing is applicable"
                }},
                "attributes": {{
                  "type": "array",
                  "description": "List of actions or scenarios derived from use case",
                  "items": {{
                    "type": "object",
                    "required": ["attribute_name", "techniquedetails"],
                    "properties": {{
                      "attribute_name": {{
                        "type": "string",
                        "description": "Name of the scenario or user action"
                      }},
                      "techniquedetails": {{
                        "type": "array",
                        "minItems": 1,
                        "description": "Steps or data points relevant to the use case",
                        "items": {{
                          "oneOf": [
                            {{ "type": "string" }},
                            {{ "type": "integer" }}
                          ]
                        }}
                      }}
                    }},
                    "additionalProperties": false
                  }}
                }}
              }},
              "additionalProperties": false
            }}
          }},
          "additionalProperties": false
        }}

        ```

        ## INSTRUCTIONS:
- DO NOT include explanation or commentary in your output.
- DO NOT alter the structure or field names in the JSON.
- Each attribute_name should be derived from the user story, requirement, or test data.
- techniquedetails must include valid, representative, and testable values.
- Respect the deduplication rule: do not reuse the same attribute or value set in multiple techniques.
- Ensure the output is valid JSON and can be parsed without error.
- Do not include fields like "$schema", "title", "type", or "properties".
- You must only return a JSON **data object** that conforms to the expected structure — NOT a schema definition.


        BEGIN YOUR ANALYSIS NOW.
        """
        messages = [
            {"role": "system",
             "content": "You are an Expert QA Agent Developed by Saksoft to Act as Quality Assurance Agent which is Thoroughly deep dive in to requirement Analysis and static Testing. You are efficient to read/understand and Create the JSON data as per given instructions"},
            {"role": "user", "content": requirment_analyzer}
        ]
        print("Total tokens in user Feature Techniques Data Generation:",
              num_tokens_from_messages(messages, model="gpt-3.5-turbo"))

        techniques_with_data = run_llm_pipeline(config, messages, TestDesignTechniques)
        # techniques_with_data = get_llm_response_pydantic2(apikey,
        #                                                   baseurl, model, messages, TestDesignTechniques)

        data = {
            "bv": techniques_with_data.boundary_value_analysis.applicable,
            "bv_details": json.dumps([attr.dict() for attr in techniques_with_data.boundary_value_analysis.attributes]),
            "ep": techniques_with_data.equivalent_class_partitioning.applicable,
            "ep_details": json.dumps(
                [attr.dict() for attr in techniques_with_data.equivalent_class_partitioning.attributes]),
            "st": techniques_with_data.state_transition_diagram.applicable,
            "st_details": json.dumps(
                [attr.dict() for attr in techniques_with_data.state_transition_diagram.attributes]),
            "dt": techniques_with_data.decision_table.applicable,
            "dt_details": json.dumps([attr.dict() for attr in techniques_with_data.decision_table.attributes]),
            "uc": techniques_with_data.use_case_testing.applicable,
            "uc_details": json.dumps([attr.dict() for attr in techniques_with_data.use_case_testing.attributes]),
        }
        sql = f"""
                    UPDATE tcg.requirments
                    SET
                        bv = %(bv)s,
                        bv_details = %(bv_details)s,
                        ep = %(ep)s,
                        ep_details = %(ep_details)s,
                        st = %(st)s,
                        st_details = %(st_details)s,
                        dt = %(dt)s,
                        dt_details = %(dt_details)s,
                        uc = %(uc)s,
                        uc_details = %(uc_details)s
                    WHERE id = {id}
                """
        execute_query_param(sql, data)
        print("*********************", techniques_with_data.model_dump_json(), "************************")
