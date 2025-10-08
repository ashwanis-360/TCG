import json
import time
from typing import Type, List

import openai
import requests
from openai import OpenAI, OpenAIError, BaseModel

from common.LLMPublisher import run_llm_pipeline
from common.llm import get_llm_response_pydantic2
from common.tokencouter import count_tokens, num_tokens_from_messages
from common.utilities import getDBRecord, execute_query_param


# Query Master Skill to  Analyse the Gap and Categorized Them
class FunctionalityList(BaseModel):
    functionalities: List[str]


class Query(BaseModel):
    question: str
    why: str


class Answer(BaseModel):
    answer: str


class QueryList(BaseModel):
    queries: List[Query]


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
#

def gapAnalyser(config, pr_id, user_story_ref):
    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={user_story_ref} and project_id={pr_id}"""
    storydetail = getDBRecord(user_story_detail, False)
    user_story = storydetail['detail']
    extract_functions = f"""You are an expert business analyst and software tester. Your goal is to analyze the given {user_story} and extract detailed functionality information that needs to be tested.

Before responding, think step-by-step through the story to understand:
- What are the key functionalities mentioned?
- What are the business rules, conditions, or validations?
- What roles are involved and what actions they can perform?
- What input data or variations might be needed?

**Instructions for Response:**
###IMPORTANT
1. Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
```json
{{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "FunctionalityList",
  "type": "object",
  "properties": {{
    "functionalities": {{
      "type": "array",
      "items": {{
        "type": "string"
      }},
      "minItems": 1
    }}
  }},
  "required": ["functionalities"],
  "additionalProperties": false
}}
```

**Rules for Output:**
1. Do NOT include any commentary or extra explanation.
2. Each functionality must be a complete sentence or detailed string.
3. Only include core, testable functionalities — no UI labels or layout references unless critical.
4. Do not repeat or paraphrase the story. Abstract and group similar actions together.

Now, here is the user story for analysis:
---
{user_story}
            """
    messages = [
        {"role": "system",
         "content": "You are an Expert QA Agent Developed by Saksoft to Act as Quality Assurance Agent which is Thoroughly deep dive in to requirement Analysis and static Testing. You are efficient to read/understand and Create the JSON data as per given instructions"},
        {"role": "user", "content": extract_functions}
    ]

    # plan = get_llm_response_pydantic2(apikey,
    #                                   baseurl, model, messages, FunctionalityList)

    print("Total tokens in Query Planner:", num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
    # print("*********************", count_tokens(messages), "************************")
    plan = run_llm_pipeline(config, messages, FunctionalityList)

    print("*********************", plan.model_dump_json(), "************************")
    final_list_oftest_cases = []
    data2 = plan.model_dump_json()
    data2_dict = json.loads(data2)
    # for activity in data2_dict['plan']:
    #     print(f"Activity: {activity['cctivity']}")
    #     for task in activity['tasks']:
    #         print(f"  - Task: {task}")
    #     print()  # Adds a newline between each activity

    for activity in data2_dict['functionalities']:
        print(activity)
        static_review_output = f"""You are a skilled QA analyst. Your task is to analyze the given **{activity}** (a functionality extracted from a user story) and list **detailed clarification questions** that are necessary to perform effective test design.

        These questions should help uncover:
        - Requirement gaps or ambiguities
        - Pre-conditions or missing dependencies
        - Edge cases or alternate flows
        - Third-party system/API interactions
        - Data requirements
        - Role-based behaviors or conditions

        Use the following input:
        - Functionality to test: **{activity}**
        - User Story context: **{user_story}**

        **Instructions for Response:**
        ###IMPORTANT
        1. Return your output strictly in the following JSON schema after you complete you thinking and reasoning:
        ```json
        {{
         
          "type": "object",
          "properties": {{
            "queries": {{
              "type": "array",
              "items": {{
                "type": "object",
                "properties": {{
                  "question": {{
                    "type": "string"
                  }},
                  "why": {{
                    "type": "string"
                  }}
                }},
                "required": ["question", "why"],
                "additionalProperties": false
              }}
            }}
          }},
          "required": ["queries","why"],
          "additionalProperties": false
        }}
        ```
        **Strict Output Rules:**
        - Your response must be a JSON object with the key "queries" pointing to an array of at least 5 valid question objects.
        - Each object must contain two non-empty string fields: "question" and "why".
        - Do NOT return any item where either field is empty, null, a placeholder, or whitespace.
        - Do NOT include incomplete entries for example : {{' ': 'why'}} or {{' ': 'question'}} or {{'question ': ''}} or {{'why ': ''}} or {{" ": " "}}.
        - Validate your output before finalizing it — all fields must have meaningful content.
        """
        messages = [
            {"role": "system",
             "content": "You are an Expert QA Agent Developed by Saksoft to Act as Quality Assurance Agent which is "
                        "Thoroughly deep dive in to requirement Analysis and static Testing. You are efficient to "
                        "read/understand and Create the JSON data as per given instructions"},
            {"role": "user", "content": static_review_output}
        ]
        print("Total tokens in Query Listing:", num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
        queries = run_llm_pipeline(config, messages, QueryList)

        # final_list_oftest_cases.append(queries.queries)

        final_list_oftest_cases.extend([q.model_dump() for q in queries.queries])
    # final_json = json.dumps([Queries for Queries in final_list_oftest_cases], indent=2)
    # final_json = json.dumps([Query.model_dump() for Query in final_list_oftest_cases], indent=2)
    print("*********************", json.dumps(final_list_oftest_cases), "************************")
    return final_list_oftest_cases


def insert_query(pr_id, user_story_ref, final_list_oftest_cases):
    new_record_ids = []

    for item in json.loads(json.dumps(final_list_oftest_cases)):
        insert_query = """
            INSERT INTO `tcg`.`qna` (`project_id`, `userstory_id`, `query`, `context`)
            VALUES (%s, %s, %s, %s);
        """

        values = (
            pr_id,
            user_story_ref,
            item["question"],
            item["why"]
        )
        qid = execute_query_param(insert_query, values)
        # q=json.loads(item)
        # print(pr_id, "***************", user_story_ref, "***************", item["question"], "***************",
        #       item["why"])
        # for data in json.dumps(final_list_oftest_cases):
        #     query_value = data["query"]
        #     why_value = data["why"]
        #     qid = execute_query_param(
        #         f"""INSERT INTO `tcg`.`qna`(`project_id`, `userstory_id`, `query`, `context`)
        #               VALUES({pr_id}, {user_story_ref}, "{query_value}", "{why_value}")"""
        #     )
        new_record_ids.append(qid)
    print("**************", new_record_ids, "**************")


def knowledge_Extrator(pr_id, user_story_ref, token, search_url):
    query_list = getDBRecord(f"""SELECT * FROM tcg.qna where project_id = {pr_id} and userstory_id={user_story_ref}""",
                             True)
    for row in query_list:
        print(row)  # prints the full row as a tuple
        # Access individual columns by index, e.g.
        search_prompt = f""""""
        print("Query:", row['query'])
        print("Context:", row['context'])
        payload = {
            "projectid": pr_id,
            "query": row['query'],
            "why": row['context']
        }

        # url = "http://127.0.0.1:8777/search"
        url = search_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            response_json = response.json()
            if response_json["answer"] != "N/A":
                execute_query_param(
                    """UPDATE tcg.qna SET answer = %s, knowledge_exist = 1 WHERE project_id = %s AND userstory_id = %s 
                    AND id = %s""",
                    (response_json["answer"], pr_id, user_story_ref, row['id'])
                )
        else:
            print("Search API return some error", response.status_code)
            # execute_query_param(
            #     f"""UPDATE tcg.qna SET answer= "{response_json["answer"]}",knowledge_exist=1 where project_id={pr_id} and userstory_id={user_story_ref} and id={row['id']}""")

def knowledge_Creater(record_id, token, search_url):
    query_list = getDBRecord(f"""SELECT * FROM tcg.qna where id = {record_id}""",
                             True)
    for row in query_list:
        print(row)  # prints the full row as a tuple
        # Access individual columns by index, e.g.
        search_prompt = f""""""
        print("Query:", row['query'])
        print("Context:", row['context'])
        knowledge="#Question :\n"+row['query']+"\n #Answer :\n"+row['answer']
        payload = {
            "project_id": row['project_id'],
            "knowledge": knowledge,

        }

        # url = "http://127.0.0.1:8777/search"
        url = search_url
        headers = {
            # "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            response_json = response.json()

        else:
            print("Add API return some error", response.status_code)
            # execute_query_param(
            #     f"""UPDATE tcg.qna SET answer= "{response_json["answer"]}",knowledge_exist=1 where project_id={pr_id} and userstory_id={user_story_ref} and id={row['id']}""")


def assumption_maker(config, pr_id, user_story_ref):
    query_list = getDBRecord(f"""SELECT * FROM tcg.qna where project_id = {pr_id} and userstory_id={user_story_ref} and 
    answer is null """, True)
    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={user_story_ref} and project_id={pr_id}"""
    storydetail = getDBRecord(user_story_detail, False)
    user_story = storydetail['detail']
    for row in query_list:
        prompt = f""" Give me the relevant and most 
        accurate answer for the Given query as {row['query']}, so that based on these assumptions test cases can be 
        design based on these assumptions. Additional context of this query is as below: **Why this question Raised :  
        
        {row['context']}
        **Instruction to follow while generating answer :
        1. Your Response should follow the JSON Structure strictly :
        {{"answer":"<Detailed Answer in String>"}}
        2. You Answer should be Json Object with key value Pair .
        3. key should always be "answer"
        4. Value of the "answer" should with Detailed answer in String formate only
        4. No, Opening and closing commentary should be included into the response.
        5. Single Key and it value is mandatory.
        """
        messages = [
            {"role": "system",
             "content": "You are an AI assistant to Answer the Question based on your knowledgebase"},
            {"role": "user", "content": prompt}
        ]
        print("Total tokens in Assumption making:", num_tokens_from_messages(messages, model="gpt-3.5-turbo"))
        answer = run_llm_pipeline(config, messages, Answer)
        # answer = get_llm_response_pydantic2(apikey,
        #                                     baseurl, model, messages, Answer)

        execute_query_param(
            """UPDATE tcg.qna SET answer = %s, knowledge_exist = 0 WHERE project_id = %s AND userstory_id = %s 
                AND id = %s""",
            (answer.answer, pr_id, user_story_ref, row['id'])
        )
# def gapAnalyser2(apikey,baseurl,model,pr_id,user_story_ref):
#     user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={user_story_ref} and project_id={pr_id}"""
#     storydetail = getDBRecord(user_story_detail, False)
#     user_story = storydetail['detail']
#     final_list_oftest_cases = []
#
#     Query_Generator = f"""Extract the list of questions in the given {user_story} which is essential to the the effective testing.
#                          ** Rule to Raise the Questions:
#                             - Question should be Very much centric to Give User story
#                             - Question Should be included UI label Details for Example Fields length, Navigation flow etc.
#                             - Question should be also Include for different error scenarios
#                             - Question should be Include Upstream and Down Stream system Integration.
#                             - Question Should be Include Business rules related queries.
#                             - Questions should be focus on functional testing area and NOT on the Infra, Process,Internal Architecture of application
#                             - Question should be more focused to identify the Early defects due to Gap in Requirement,Ambiguities in requirement, Unclear requirement,Pre-Requisites, 3rd Party Data Dependencies, API Integrations which more important for Test Designing, Data Designing and test execution
#                          ** Instruction for the the response:
#                             1. Your Response should follow the JSON Structure strictly : {{"queries":[{{"question":"<Questions asked by you>","why": "<Why this Question is asked>"}},{{<Other Questions>}}]
#                             2. All the questions and why should be in string and detailed and focusing on the functionality only.
#                             3. Response should contains only list on Queries details in Provided JSON format.
#                             4. No, Opening and closing commentary should be included into the response.
#                             5. All the Attributes in Provided JSON is Mandatory.
#                      """
#     messages = [
#         {"role": "system", "content": "You are an AI assistant to understand and Give user story and listing out different functionalities to be tested"},
#         {"role": "user", "content": Query_Generator}
#     ]
#
#     queries = get_llm_response_pydantic2(apikey,
#                                           baseurl, model, messages, QueryList)
#
#     print("*********************", queries.model_dump_json(), "************************")
#     final_list_oftest_cases.extend([q.model_dump() for q in queries.queries])
#     print("*********************", final_list_oftest_cases, "************************")
#     return final_list_oftest_cases
