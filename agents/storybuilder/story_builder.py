from typing import List, Type
import json
from pydantic import BaseModel
from openai import OpenAI, OpenAIError
import openai
import time

from common.LLMPublisher import run_llm_pipeline
from common.llm import get_llm_response_pydantic2
from common.tokencouter import num_tokens_from_messages
from common.utilities import getDBRecord, execute_query_param


class UserStoryModel(BaseModel):
    prerequesites: List[str]
    summary: str
    actions: List[str]
    test_data: List[str]
    acceptance_criteria: List[str]


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


def building_story(config, userstrory_ref):
    ## Reading Questions And Answer and Storing into QNA
    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={userstrory_ref}"""
    storydetail = getDBRecord(user_story_detail, False)
    pr_id = storydetail['project_id']
    userstory = storydetail['detail']
    Enriched_user_story_prompt = f"""
        You are an AI Agent specialized in Requirement Understanding and Enrichment. Given a user story, your task is to analyze, reason, and generate a structured enriched version of it. Your enrichment must include the following five attributes derived strictly from the user story and logical inferences as per instructions.

    ### TASK: Enrich the given user story: {userstory}

    ---

    **Instructions for Response:**
        ###IMPORTANT
        1. Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
    ```json
    {{
     
      "title": "UserStoryModel",
      "type": "object",
      "properties": {{
        "prerequesites": {{
          "type": "array",
          "items": {{
            "type": "string"
          }},
          "minItems": 1
        }},
        "summary": {{
          "type": "string",
          "minLength": 1
        }},
        "actions": {{
          "type": "array",
          "items": {{
            "type": "string"
          }},
          "minItems": 1
        }},
        "test_data": {{
          "type": "array",
          "items": {{
            "type": "string"
          }},
          "minItems": 1
        }},
        "acceptance_criteria": {{
          "type": "array",
          "items": {{
            "type": "string"
          }},
          "minItems": 1
        }}
      }},
      "required": [
        "prerequesites",
        "summary",
        "actions",
        "test_data",
        "acceptance_criteria"
      ],
      "additionalProperties": false
    }}
    ```
    ⚠️ Do not include any introductory or closing text. Only respond with a valid JSON object as specified above. All five fields are mandatory.

    ---

    ### Attribute Instructions and Reasoning Guidance:

    **1. "prerequesites"**
    - List *all required preconditions* to execute the user story.
    - Must include:
      - Required user roles or access rights
      - Any preloaded or available system data
      - Availability or status of upstream/downstream systems or APIs
      - Authentication or environment setup needs

    **2. "summary"**
    - Generate a *crisp, functional summary* of the user story.
    - It must reflect *what* functionality is being delivered without detailing *how*.

    **3. "actions"**
    - List the *end-to-end functional steps* a user or system performs in this user story.
    - Avoid excessive granularity or step numbers.
    - Do **not** prefix with "Step 1", "1.", etc.
    - Group similar activities when appropriate (e.g., "Fill user details and submit form").

    **4. "test_data"**
    - Identify all input data *required for testing or execution*.
    - Only include data *explicitly required to be input*, fetched from other systems, or configured beforehand.
    - Each item should be a *string* representing the name of the input field or data element.
    - Do NOT include output/validation data.

    **5. "acceptance criteria"**
    - Elaborate on all existing acceptance criteria in the user story.
    - Ensure the criteria cover:
      - End-to-end data flow and backend validation
      - UI flow and interface navigation
      - UI and field-level validation
      - API and system integration behavior
      - Business rule validations
      - Authentication/authorization (if applicable)
      - Any visual or functional UI changes mentioned
    - Add any *missing* but logically necessary acceptance criteria based on the user story.

    ---

    ### Execution Note:
    - You must reason thoroughly and use structured thinking before writing each section.
    - Ensure JSON format is always syntactically valid.
    - Do not leave any of the fields empty.
    - Be concise yet complete in each attribute.




                """
    messages = [
        {"role": "system",
         "content": "You are an AI Technical Business Analyst developed by SakSoft who enriched the user story and structure if in well defined structure which is easy to understand for the Dev, QA and Other Non Technical Stakeholder.You are efficient to read/understand and Create the JSON data as per given instructions"},
        {"role": "user", "content": Enriched_user_story_prompt}
    ]
    print("Total tokens in user Story building:", num_tokens_from_messages(messages, model="gpt-3.5-turbo"))

    enriched_userstory = run_llm_pipeline(config, messages, UserStoryModel)
    # enriched_userstory = get_llm_response_pydantic2(apikey,
    #                                                 baseurl, model, messages, UserStoryModel)
    print("*********************", enriched_userstory.model_dump_json(), "************************")
    try:

        query = """
            INSERT INTO `tcg`.`story_details`
                (`project_id`, `userstory_id`, `pre_requsite`, `summary`, `actions`, `test_data`, `acceptance_criteria`)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s);
        """

        params = (
            pr_id,
            userstrory_ref,
            json.dumps(enriched_userstory.prerequesites),
            enriched_userstory.summary,
            json.dumps(enriched_userstory.actions),
            json.dumps(enriched_userstory.test_data),
            json.dumps(enriched_userstory.acceptance_criteria)
        )

        execute_query_param(query, params)

    except Exception as e:

       print("************* Something went Wrong *************")

