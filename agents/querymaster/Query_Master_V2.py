import json
from typing import List, Dict, Type
from pydantic import BaseModel

from common.LLMPublisher import run_llm_pipeline
from common.tokencouter import num_tokens_from_messages
from common.utilities import getDBRecord, execute_query_param


# -----------------------------
# Pydantic Models
# -----------------------------

class Question(BaseModel):
    category: str
    question: str
    why: str
    priority: str


class StaticAnalysisOutput(BaseModel):
    questions: List[Question]

class Answer(BaseModel):
    answer: str
# -----------------------------
# Static Analysis Agent
# -----------------------------

def gapAnalyser(config, pr_id, user_story_ref) -> List[Dict]:
    """
    Production grade Static Testing Agent.
    Generates clarification questions required for full test design coverage
    for Web Applications and API integrations.
    """
    user_story_detail = f"""SELECT project_id,detail FROM tcg.userstory where _id={user_story_ref} and project_id={pr_id}"""
    storydetail = getDBRecord(user_story_detail, False)
    user_story = storydetail['detail']
    # user_story = "Login into Application"
    prompt = f"""
You are a Senior QA Architect performing static testing on a software requirement.

Your task is to analyze the provided user story and generate clarification questions required
for designing complete test coverage for a WEB APPLICATION and API integrations.

Your questions must cover the following testing areas:

1. Workflow Testing
2. Form and Field Validation
3. UI / UX Behaviour
4. Navigation Behaviour
5. Authorization and Actor Roles
6. Negative Testing
7. System Integration and API Behaviour
8. Data Handling and Persistence

-------------------------
Guidelines
-------------------------

Workflow Testing
- Identify business workflows
- Confirm alternate flows
- Validate workflow completion states

Form and Field Validation
- Mandatory field validation
- Optional field behaviour
- Field format validation
- Length validation
- Error message validation

UI / UX Validation
- Field visibility
- Field order
- Conditional fields
- Layout consistency
- Font and color adherence
- Keyboard navigation (tab order)

Navigation Behaviour
- Browser back button
- Browser forward button
- Direct URL access
- Session handling across multiple tabs

Authorization Testing
- Role based access control
- Permission restrictions
- Actor level access

Negative Testing
- Unauthorized access
- Invalid token usage
- Manipulated requests
- Invalid inputs

Integration Testing
- Downstream system updates
- API interactions
- Data synchronization

Data Handling
- Data persistence validation
- Data consistency across systems
- Data format validation

-------------------------
Response Format
-------------------------

Return JSON only with the following schema:

{{
 "questions":[
   {{
     "category":"Workflow | Form Validation | UI/UX | Navigation | Authorization | Negative | Integration | Data",
     "question":"string",
     "why":"string",
     "priority":"High | Medium | Low"
   }}
 ]
}}

Rules:
- Each question must be relevant for test design.
- Avoid duplicates.
- Each category should have at least 2 questions if applicable.
- Do NOT add explanation outside JSON.
- Questions must be clear and precise.

-------------------------
User Story
-------------------------

{user_story}

"""

    messages = [
        {
            "role": "system",
            "content": "You are an expert QA architect specialized in requirement analysis and static testing."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    # Run LLM
    result = run_llm_pipeline(config, messages, StaticAnalysisOutput)

    # Convert to list of dict
    return [q.model_dump() for q in result.questions]

def assumption_maker(config, pr_id, user_story_ref):

    # Fetch unanswered questions
    query_list = getDBRecord(
        f"""
        SELECT * 
        FROM tcg.qna 
        WHERE project_id = {pr_id} 
        AND userstory_id = {user_story_ref} 
        AND answer IS NULL
        """,
        True
    )

    # Fetch user story
    user_story_detail_query = f"""
        SELECT project_id, detail 
        FROM tcg.userstory 
        WHERE _id = {user_story_ref} 
        AND project_id = {pr_id}
    """

    storydetail = getDBRecord(user_story_detail_query, False)
    user_story = storydetail['detail']

    for row in query_list:

        prompt = f"""
You are a **Senior QA Architect certified in ISTQB standards**.

When product documentation or requirements are incomplete, your role is to generate **practical testing assumptions** that QA engineers can safely use while designing test cases.

### User Story
{user_story}

### QA Question
{row['query']}

### Why this question was raised
{row['context']}

### Task
Generate **one realistic QA assumption** that helps testers design test cases when the requirement is unclear.

### Rules for Assumption Creation
1. The assumption must follow **ISTQB testing best practices**.
2. The assumption must be **practical, realistic, and testable**.
3. The assumption must **not invent complex business logic**.
4. Prefer **industry standard system behaviour** used in most applications.
5. The assumption must be **2-3 sentence only**.
6. Maximum **50 words**.
7. Start the sentence with **"Assume that"**.
8. Avoid explanation, reasoning, or background text.

### Output Format
Return strictly a JSON object:

{{"answer": "<ISTQB grade QA assumption>"}}
"""

        messages = [
            {
                "role": "system",
                "content": "You are a Senior QA Architect generating concise, realistic testing assumptions following ISTQB testing standards."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        print(
            "Total tokens in Assumption making:",
            num_tokens_from_messages(messages, model="gpt-3.5-turbo")
        )

        try:

            answer = run_llm_pipeline(config, messages, Answer)

            if not answer or not answer.answer:
                raise ValueError("Empty assumption returned from LLM")

            execute_query_param(
                """
                UPDATE tcg.qna 
                SET answer = %s, knowledge_exist = 0 
                WHERE project_id = %s 
                AND userstory_id = %s 
                AND id = %s
                """,
                (answer.answer.strip(), pr_id, user_story_ref, row['id'])
            )

        except Exception as e:

            print(f"Assumption generation failed for QNA ID {row['id']}: {str(e)}")

            fallback_assumption = "Assume that the system follows standard web application behavior when processing this functionality."

            execute_query_param(
                """
                UPDATE tcg.qna 
                SET answer = %s, knowledge_exist = 0 
                WHERE project_id = %s 
                AND userstory_id = %s 
                AND id = %s
                """,
                (fallback_assumption, pr_id, user_story_ref, row['id'])
            )
