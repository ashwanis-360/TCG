import io
import json
import os
from base64 import b64encode
from typing import List, Optional
import datetime
from xmlrpc.client import DateTime as XMLRPCDateTime
import docx
import pandas as pd
import requests
from docx.oxml.ns import qn
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
import asyncio
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from flask import jsonify
from pydantic import BaseModel
import PyPDF2
from adaptors.pm.JIRAAdaptor import JiraAdapter
from adaptors.tm.kiwi import KiwiPublisher
from adaptors.tm.testiny import TestinyPublisher
from agents.querymaster.Query_Master import knowledge_Creater
from common.TestCasePublisher import TestCasePublisher
from broker import background_task, babackground_task, resume_task
from common.pm_factory import PMFactory
from common.tokencouter import num_tokens_from_messages
from common.utilities import TokenData, get_current_user, create_bold_paragraph, create_ordered_list, \
    extract_file_content
import extract_msg
from common.utilities import execute_query_param, getDBRecord, execute_query_with_values, safe_json_load, \
    fetch_all, prepare_excel2
import email
from email import policy
from email.parser import BytesParser

app = FastAPI()
task_lock = asyncio.Lock()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#
# class QueryRequest(BaseModel):
#     query: str
#     why: str
#
#
# class QueryResponse(BaseModel):
#     query: str
#     why: str
#     answer: str


async def run_task_with_lock(input_data, userstory_ref, pr_id, token):
    async with task_lock:  # Only one task can acquire this lock at a time
        await background_task(input_data, userstory_ref, pr_id, token)


@app.post("/process/")
async def process_data(input_data: dict, background_tasks: BackgroundTasks,
                       user: TokenData = Depends(get_current_user)):
    username = user.username
    roles = user.roles
    print("INFO : Authentication Token=",user.token," Requested Payload =",input_data)
    # print(user.token)
    # print(input_data)
    # logger.info("User story submitted "+input_data['user_input']+" by user "+username)
    if 2 in roles:
        pr_id = input_data['pr_id']
        user_story_input = input_data['user_input']
        autopilot = input_data.get("autopilot", False)
        external_refe = None
        try:
            external_refe = input_data['key']
        except Exception as e:
            external_refe = None
        # logger.info("ALM ID for User story is"+external_refe)
        #
        userstory_ref = execute_query_param(
            """
            		INSERT INTO `tcg`.`userstory`
                	(`project_id`, `detail`, `reference_key`, `status`, `owner`,`autopilot`)
            		VALUES (%s, %s, %s, %s, %s, %s);
            	""",
            (pr_id, user_story_input, external_refe, "in-progress", 1, autopilot)
        )
        background_tasks.add_task(background_task, userstory_ref, pr_id, user.token)

        # Return 202 response immediately
        return JSONResponse(
            content={"message": "Request accepted", "request_id": userstory_ref, "reference_key": external_refe},
            status_code=202)
    elif 5 in roles:

        user_story_input = input_data['user_input']
        insert_idea_query = """
                            INSERT INTO tcg.intial_idea (input)
                            VALUES (%s)
                        """
        id = execute_query_param(insert_idea_query, (
            user_story_input,
        ))

        background_tasks.add_task(babackground_task, user_story_input, id, user.token)

        # Return 202 response immediately
        return JSONResponse(
            content={"message": "Request accepted", "request_id": id},
            status_code=202)

    else:
        return JSONResponse(content={"message": "Request rejected"}, status_code=401)

@app.post("/process/v2")
async def process_data_additional_details( pr_id: int = Form(...),
    user_input: str = Form(...),
    autopilot: bool = Form(None),
    key: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    user: TokenData = Depends(get_current_user),
    additional_context: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
                                           ):
    username = user.username
    roles = user.roles
    print(user.token)


    # logger.info("User story submitted "+input_data['user_input']+" by user "+username)
    if 2 in roles:
        pr_id = pr_id
        # try:
        #     pr_id = int(pr_id) if pr_id and pr_id.strip().isdigit() else None
        # except ValueError:
        #     project_id = None
        user_story_input = user_input
        autopilot = autopilot
        external_refe = None
        try:
            external_refe = key
        except Exception as e:
            external_refe = None
        # logger.info("ALM ID for User story is"+external_refe)
        #
        # if (not additional_context or additional_context.strip() == "") and not files:
        #     raise HTTPException(
        #         status_code=400,
        #         detail="At least one of 'text' or 'files' must be provided."
        #     )

            # --- Extract File Contents ---
        results = {}
        if files:
            for file in files:
                results[file.filename] = await extract_file_content(file)

        # --- Combine Text + File Content ---
        final_parts = []
        final_parts.append(user_input)
        final_parts.append("Additional Context Provided")
        if additional_context and additional_context.strip():
            final_parts.append(additional_context.strip())
        final_parts.append("Detailed Fetched From Uploaded Documents")
        if files:
            for fname, fcontent in results.items():
                final_parts.append(f"\n\n{fcontent.strip()}")

        final_extracted_text = "\n".join(final_parts)
        print("\n--- Extracted Content ---\n", final_extracted_text, "\n--- End ---\n")

        userstory_ref = execute_query_param(
            """
            		INSERT INTO `tcg`.`userstory`
                	(`project_id`, `detail`, `reference_key`, `status`, `owner`,`autopilot`)
            		VALUES (%s, %s, %s, %s, %s, %s);
            	""",
            (pr_id, final_extracted_text, external_refe, "in-progress", 1, autopilot)
        )
        print("Total tokens in Query Planner:", num_tokens_from_messages(final_extracted_text, model="gpt-3.5-turbo"))
        background_tasks.add_task(background_task, userstory_ref, pr_id, user.token)

        # Return 202 response immediately
        return JSONResponse(
            content={"message": "Request accepted", "request_id": userstory_ref, "reference_key": external_refe},
            status_code=202)
    elif 5 in roles:

        user_story_input = user_input
        insert_idea_query = """
                            INSERT INTO tcg.intial_idea (input)
                            VALUES (%s)
                        """
        id = execute_query_param(insert_idea_query, (
            user_story_input,
        ))

        background_tasks.add_task(babackground_task, user_story_input, id, user.token)

        # Return 202 response immediately
        return JSONResponse(
            content={"message": "Request accepted", "request_id": id},
            status_code=202)

    else:
        return JSONResponse(content={"message": "Request rejected"}, status_code=401)


@app.post("/next/{userstoryid}")
async def resume(userstoryid: int, background_tasks: BackgroundTasks, user: TokenData = Depends(get_current_user)):
    username = user.username
    roles = user.roles
    print(user.token)
    print("i am here for sure")
    # logger.info("User story submitted "+input_data['user_input']+" by user "+username)
    if 2 in roles:
        # Check the Over All Status
        # if Error Then Re-try
        # else if Hold the read the Current stage
        # update the Stage in DB by incrementing by 1
        # Based on the updated Stage call the Method
        background_tasks.add_task(resume_task, userstoryid, user.token)

        # Return 202 response immediately
        return JSONResponse(
            content={"message": "Request accepted", "request_id": userstoryid},
            status_code=202)


@app.get("/get_list_user_story_details/")
def get_story_updates(pr_id: str, user: TokenData = Depends(get_current_user)):
    # Get the parameters from the request
    username = user.username
    roles = user.roles
    if 2 in roles:
        qna_details = f"""select _id,project_id,detail,status,reference_key,Error_details,stage,DATE_FORMAT(created, '%Y-%m-%dT%H:%i:%s') AS created,
    DATE_FORMAT(updated, '%Y-%m-%dT%H:%i:%s') AS updated FROM tcg.userstory 
                    where project_id={pr_id}"""
        # Query the MySQL database for matching records
        list_userstory = getDBRecord(qna_details, True)
        result = {
            'list': list_userstory,

        }

        return JSONResponse(content={"message": result}, status_code=200)
    else:
        return JSONResponse(content={"message": "Request rejected"}, status_code=401)


#
@app.get('/download-excel')
def download_excel(pr_id: str, user_story_id: str, user: TokenData = Depends(get_current_user)):
    # Fetch data from database
    username = user.username
    roles = user.roles
    if 2 in roles:

        testcases = f"""SELECT id as testcase_id,external_ref as alm_id,project_id as Project_Name,userstory_id as user_story_ID,COALESCE(
        (SELECT detail FROM tcg.requirments WHERE id = tc.requirment_id and userstory_id={user_story_id} ), 
        (SELECT description FROM tcg.planning_item WHERE _id = tc.requirment_id and userstory_id={user_story_id})
    ) AS requirement_detail, summary as scenario,test_steps,test_data,expected_result,accepted FROM tcg.test_cases tc
                          WHERE project_id={pr_id} AND userstory_id={user_story_id}"""
        # Query the MySQL database for matching records
        list_testcases = getDBRecord(testcases, True)
        df = pd.DataFrame(list_testcases)
        # Create an Excel file in memory
        output = prepare_excel2(pr_id, user_story_id, df)
        return StreamingResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": "attachment; filename=data.xlsx"}
        )
    else:
        return JSONResponse(content={"message": "Request rejected"}, status_code=401)


@app.get("/get_update/")
def get_updates(pr_id: str, user_story_ref: str, user: TokenData = Depends(get_current_user)):
    # Get the parameters from the request
    username = user.username
    roles = user.roles
    if 2 in roles:
        project_id = pr_id
        user_story_id = user_story_ref
        qna_details = f"""select id, query as query,context as why,answer as assumptions,knowledge_exist FROM tcg.qna 
            where project_id={project_id} and userstory_id={user_story_id}"""
        qna = getDBRecord(qna_details, True)
        if not qna:
            qna = None

        detailed_userstory = f"""select id,pre_requsite as pre_requsite,summary as summary, actions,test_data,acceptance_criteria FROM tcg.story_details 
                            where project_id={project_id} and userstory_id={user_story_id}"""
        # Query the MySQL database for matching records
        details_story = getDBRecord(detailed_userstory, True)

        if not details_story:
            details_story = None
        user_story_object = None
        if details_story is not None:
            user_story_object = {
                "id": details_story[0]['id'],
                "pre_requsite": details_story[0]['pre_requsite'].decode('utf-8'),
                "summary": details_story[0]['summary'],
                "actions": json.loads(details_story[0]['actions'].decode('utf-8')),
                "test_data": json.loads(details_story[0]['test_data'].decode('utf-8')),
                "acceptance_criteria": json.loads(details_story[0]['acceptance_criteria'].decode('utf-8'))
            }

        requirmentdetails = f"""select id,detail,type,data,test_steps,bv,bv_details,ep,ep_details,st,st_details,dt,dt_details,uc,uc_details FROM tcg.requirments 
                            where project_id={project_id} and userstory_id={user_story_id}"""
        requirmentdetails = getDBRecord(requirmentdetails, True)
        # print("result_returned", result[1]['query'])
        # Return the result as JSON
        if not requirmentdetails:
            requirmentdetails = None

        # JSONResponse(content={"stage": "1","stage_id":1 "updates": jsonify(result)}, status_code=200)
        requirement_details = []
        if requirmentdetails is not None:
            for row in requirmentdetails:
                tempdata = {
                    "id": row['id'],
                    "detail": row['detail'],
                    "type": row['type'],
                    "data": safe_json_load(row['data'].decode('utf-8')) if row['data'] else None,
                    "test_steps": safe_json_load(row['test_steps'].decode('utf-8')),
                    "bv": row['bv'],
                    "bv_details": safe_json_load(row['bv_details'].decode('utf-8')) if row['bv_details'] else None,
                    "ep": row['ep'],
                    "ep_details": safe_json_load(row['ep_details'].decode('utf-8')) if row['ep_details'] else None,
                    "st": row['st'],
                    "st_details": safe_json_load(row['st_details'].decode('utf-8')) if row['st_details'] else None,
                    "dt": row['st'],
                    "dt_details": safe_json_load(row['dt_details'].decode('utf-8')) if row['dt_details'] else None,
                    "uc": row['uc'],
                    "uc_details": safe_json_load(row['uc_details'].decode('utf-8')) if row['uc_details'] else None,

                }
                requirement_details.append(tempdata)

        test_cases = f"""SELECT id,requirment_id,COALESCE(
        (SELECT detail FROM tcg.requirments WHERE id = requirment_id and userstory_id={user_story_id} ), 
        (SELECT description FROM tcg.planning_item WHERE _id = requirment_id and userstory_id={user_story_id}) ) AS 
        requirment_detail,technique,summary ,test_steps ,expected_result,test_data,accepted,priority,regression,tobeautomate,external_ref FROM 
        tcg.test_cases where project_id={project_id} and userstory_id={user_story_id}  order by requirment_id asc"""
        # Query the MySQL database for matching records
        test_cases_list = getDBRecord(test_cases, True)
        # print("result_returned", result[1]['query'])
        # Return the result as JSON

        tech_mapping = {
            "Boundary Value Analysis": "bva",
            "Equivalent Class Partitioning": "ecp",
            "Decision Table Testing": "dtt",
            "State Transitioning": "st",
            "Use Case Testing": "uc"
        }
        if not test_cases_list:
            test_cases_list = None
        finaltest_cases_list = []
        if test_cases_list is not None:
            for row in test_cases_list:

                print("$$$$$$$$$$$$$$$$$$$$$$ ", row['id'], "")
                tempdata = {
                    "id": row['id'],
                    "requirment_id": row['requirment_id'],
                    "requirment_summary": row['requirment_detail'],
                    "technique": tech_mapping.get(row['technique'], row['technique']),
                    "summary": row['summary'],
                    "test_steps": safe_json_load(row['test_steps'].decode('utf-8')),
                    "expected_result": row['expected_result'],
                    "test_data": safe_json_load(row['test_data'].decode('utf-8')),
                    "accepted": row['accepted'],
                    "priority": row['priority'],
                    "tobeautomate": row['tobeautomate'],
                    "regression": row['regression'],
                    "external_id":row['external_ref'],
                    "published": True if row['external_ref'] is not None else False
                }
                finaltest_cases_list.append(tempdata)
        # JSONResponse(content={"stage": "1","stage_id":1 "updates": jsonify(result)}, status_code=200)

        result = {
            'qna': qna,
            'user_story': user_story_object,
            'requirement_details': requirement_details,
            'test_cases': finaltest_cases_list

        }

        return JSONResponse(content={"message": result}, status_code=200)
    else:
        return JSONResponse(content={"message": "Request rejected"}, status_code=401)


@app.post("/update_review_status")
async def update_review_status(input_data: dict,
                               user: TokenData = Depends(get_current_user)):
    username = user.username
    testcase_id = input_data['test_case_id']
    accepted_status = input_data['accepted']
    roles = user.roles
    if 2 in roles:
        # test_review_status_update = f"""select _id,project_id,detail,status,reference_key FROM tcg.userstory
        #                where project_id={pr_id}"""
        test_review_status_update = f"""UPDATE `tcg`.`test_cases` SET `accepted` = {accepted_status} WHERE (`id` = {testcase_id});"""
        # Query the MySQL database for matching records
        list_userstory = execute_query_param(test_review_status_update)
        # result = {
        #     'list': list_userstory,
        #
        # }
    return JSONResponse(content={"message": "Test cases accepted"}, status_code=200)


@app.post("/publish_testcase")
async def publish_testcase(input_data: dict,
                           user: TokenData = Depends(get_current_user)):
    print("in Comming Payload from UI",input_data )
    publisher = TestCasePublisher(user, input_data['userstory_ref_id'],input_data)
    tool = publisher.integration['tool']
    print("Tool from API: ", tool)
    tool_map = {
        "testiny": TestinyPublisher,
        "kiwi": KiwiPublisher
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    success = tool_publisher.publish(input_data)

    if success:
        return JSONResponse(content={"message": f"Published to {tool.title()} successfully"}, status_code=200)
    else:
        return JSONResponse(content={"message": f"Failed to publish to {tool.title()}"}, status_code=500)


@app.post("/publish_user_story")
async def publish_us(input_data: dict,
                     user: TokenData = Depends(get_current_user)):
    userstory = input_data['userstory_ref_id']
    project_id = input_data['project_id']

    publisher = PMFactory(user, project_id)
    tool = publisher.integration['tool']
    Additonal_Config = publisher.integration['additional_config']

    tool_map = {
        "jira": JiraAdapter,
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    userstory_query = """
               SELECT id,prerequesites, summary, actions, test_data, acceptance_criteria
               FROM ideated_user_story
               WHERE id = %s
           """
    userstories = fetch_all(userstory_query, (userstory,))
    if userstories:
        row = userstories[0]

        # If the list-type fields are stored as strings (either JSON or comma-separated), parse them:
        def parse_field(field):
            if isinstance(field, str):
                try:
                    return json.loads(field)  # if stored as JSON array string
                except json.JSONDecodeError:
                    return [item.strip() for item in field.split(',')]  # fallback to CSV
            return field

        result_json = {
            "id": row["id"],
            "prerequesites": parse_field(row["prerequesites"]),
            "summary": row["summary"],
            "actions": parse_field(row["actions"]),
            "test_data": parse_field(row["test_data"]),
            "acceptance_criteria": parse_field(row["acceptance_criteria"])
        }

        description_content = []

        # Pre-requisites
        description_content.append(create_bold_paragraph("Pre-requisite:"))
        description_content.append(create_ordered_list(result_json["prerequesites"]))

        # Actions
        description_content.append(create_bold_paragraph("Actions:"))
        description_content.append(create_ordered_list(result_json["actions"]))

        # Test Data
        description_content.append(create_bold_paragraph("Test Data:"))
        description_content.append(create_ordered_list(result_json["test_data"]))

        # Acceptance Criteria (optional)
        description_content.append(create_bold_paragraph("Acceptance Criteria:"))
        description_content.append(create_ordered_list(result_json["acceptance_criteria"]))

        create_result = tool_publisher.create_ticket({
            "project_key": Additonal_Config["project"],
            "summary": row["summary"],
            "description": description_content,
            "issue_type": "Story"
        })
        # success = tool_publisher.read({"project": "KAN", "status": "TO DO"})

        if create_result:
            return JSONResponse(content=create_result, status_code=200)
        else:
            return JSONResponse(content={"message": f"Failed to Write {tool.title()}"}, status_code=500)


@app.post("/append_user_story")
async def update_us(input_data: dict,
                    user: TokenData = Depends(get_current_user)):
    userstory = input_data['userstory_ref_id']
    project_id = input_data['project_id']
    print("******", userstory, "******", project_id)
    publisher = PMFactory(user, project_id)
    tool = publisher.integration['tool']
    tool_map = {
        "jira": JiraAdapter,
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    userstory_query = """
               SELECT id,pre_requsite, summary, actions, test_data, acceptance_criteria
               FROM story_details
               WHERE userstory_id = %s
           """

    userstories = fetch_all(userstory_query, (userstory,))
    print("****** list of user story", userstories)
    userstory_key = """
                   SELECT reference_key
                   FROM userstory
                   WHERE _id = %s
               """
    ticket_id_list = fetch_all(userstory_key, (userstory,))
    ticket_id = ticket_id_list[0]["reference_key"]
    print("******list of ref_id", ticket_id)
    if userstories:
        row = userstories[0]

        # If the list-type fields are stored as strings (either JSON or comma-separated), parse them:
        def parse_field(field):
            if isinstance(field, bytes):
                field = field.decode("utf-8")
            if isinstance(field, str):
                try:
                    return json.loads(field)  # if stored as JSON array string
                except json.JSONDecodeError:
                    return [item.strip() for item in field.split(',')]  # fallback to CSV
            return field

        result_json = {
            "id": row["id"],
            "prerequesites": parse_field(row["pre_requsite"]),
            "summary": row["summary"],
            "actions": parse_field(row["actions"]),
            "test_data": parse_field(row["test_data"]),
            "acceptance_criteria": parse_field(row["acceptance_criteria"])
        }
        print("******", result_json, )
        description_content = []

        # Pre-requisites
        description_content.append(create_bold_paragraph("Pre-requisite:"))
        description_content.append(create_ordered_list(result_json["prerequesites"]))

        # Actions
        description_content.append(create_bold_paragraph("Actions:"))
        description_content.append(create_ordered_list(result_json["actions"]))

        # Test Data
        description_content.append(create_bold_paragraph("Test Data:"))
        description_content.append(create_ordered_list(result_json["test_data"]))

        # Acceptance Criteria (optional)
        description_content.append(create_bold_paragraph("Acceptance Criteria:"))
        description_content.append(create_ordered_list(result_json["acceptance_criteria"]))

        # Update the ticket
        print(description_content)
        update_result = tool_publisher.update({
            "ticket_key": ticket_id,
            "description": description_content
        })
        print(update_result)
        # update_result = tool_publisher.update({
        #     "project_key": "KAN",
        #     "summary": row["summary"],
        #     "description": description_content,
        #     "issue_type": "Story",
        #     "ticket_key": ticket_id
        # })
        # success = tool_publisher.read({"project": "KAN", "status": "TO DO"})

        if update_result:
            return JSONResponse(content=update_result, status_code=200)
        else:
            return JSONResponse(content={"message": f"Failed to Write {tool.title()}"}, status_code=500)


@app.post("/update_user_story")
async def publish_us(input_data: dict,
                     user: TokenData = Depends(get_current_user)):
    userstory = input_data['userstory_ref_id']
    project_id = input_data['project_id']

    publisher = PMFactory(user, project_id)
    tool = publisher.integration['tool']
    tool_map = {
        "jira": JiraAdapter,
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    userstory_query = """
               SELECT id,prerequesites, summary, actions, test_data, acceptance_criteria
               FROM ideated_user_story
               WHERE id = %s
           """
    userstories = fetch_all(userstory_query, (userstory,))
    if userstories:
        row = userstories[0]

        # If the list-type fields are stored as strings (either JSON or comma-separated), parse them:
        def parse_field(field):
            if isinstance(field, str):
                try:
                    return json.loads(field)  # if stored as JSON array string
                except json.JSONDecodeError:
                    return [item.strip() for item in field.split(',')]  # fallback to CSV
            return field

        result_json = {
            "id": row["id"],
            "prerequesites": parse_field(row["prerequesites"]),
            "summary": row["summary"],
            "actions": parse_field(row["actions"]),
            "test_data": parse_field(row["test_data"]),
            "acceptance_criteria": parse_field(row["acceptance_criteria"])
        }

        description_content = []

        # Pre-requisites
        description_content.append(create_bold_paragraph("Pre-requisite:"))
        description_content.append(create_ordered_list(result_json["prerequesites"]))

        # Actions
        description_content.append(create_bold_paragraph("Actions:"))
        description_content.append(create_ordered_list(result_json["actions"]))

        # Test Data
        description_content.append(create_bold_paragraph("Test Data:"))
        description_content.append(create_ordered_list(result_json["test_data"]))

        # Acceptance Criteria (optional)
        description_content.append(create_bold_paragraph("Acceptance Criteria:"))
        description_content.append(create_ordered_list(result_json["acceptance_criteria"]))

        create_result = tool_publisher.create_ticket({
            "project_key": "KAN",
            "summary": row["summary"],
            "description": description_content,
            "issue_type": "Story"
        })
        # success = tool_publisher.read({"project": "KAN", "status": "TO DO"})

        if create_result:
            return JSONResponse(content=create_result, status_code=200)
        else:
            return JSONResponse(content={"message": f"Failed to Write {tool.title()}"}, status_code=500)


@app.post("/update_testcase")
async def update_testcase(input_data: dict,
                          user: TokenData = Depends(get_current_user)):
    username = user.username
    roles = user.roles
    if 2 in roles:
        data = input_data

        # Extract the ID and check if it's provided
        record_id = data.get("id")
        if not record_id:
            return jsonify({"error": "ID is required"}), 400

        # Prepare the fields to update
        print(data.items())
        fields = {key: value for key, value in data.items() if
                  key in ['summary', 'test_steps', 'expected_result', 'test_data', 'tobeautomate',
                          'regression'] and key != 'id'}

        # Return an error if no fields are provided to update
        if not fields:
            return jsonify({"error": "At least one field to update is required"}), 400

        # Construct the SQL query
        set_clause = ', '.join(f"{column} = %s" for column in fields)
        query = f"UPDATE `tcg`.`test_cases` SET {set_clause} WHERE id = %s"

        # Prepare the values for the placeholders in the SQL query
        values = list(fields.values()) + [record_id]
        print(query)
        print(values)
        execute_query_with_values(query, values)
    return JSONResponse(content={"message": "Testcases updated"}, status_code=200)


@app.post("/update_requirement")
async def update_requirement(input_data: dict,
                             user: TokenData = Depends(get_current_user)):
    username = user.username
    roles = user.roles
    if 2 in roles:
        data = input_data

        # Extract the ID and check if it's provided
        record_id = data.get("id")
        if not record_id:
            return jsonify({"error": "ID is required"}), 400

        # Prepare the fields to update
        fields = {key: value for key, value in data.items() if
                  key in ['detail', 'type', 'data', 'test_steps'] and key != 'id'}

        # Return an error if no fields are provided to update
        if not fields:
            return jsonify({"error": "At least one field to update is required"}), 400

        # Construct the SQL query
        set_clause = ', '.join(f"{column} = %s" for column in fields)
        query = f"UPDATE `tcg`.`requirments` SET {set_clause} WHERE id = %s"

        # Prepare the values for the placeholders in the SQL query
        values = list(fields.values()) + [record_id]
        print(query)
        print(values)
        execute_query_with_values(query, values)

    return JSONResponse(content={"message": "Requirement updated"}, status_code=200)


@app.post("/update_userstory")
async def update_userstory(input_data: dict,
                           user: TokenData = Depends(get_current_user)):
    username = user.username
    roles = user.roles
    if 2 in roles:
        data = input_data

        # Extract the ID and check if it's provided
        record_id = data.get("id")
        if not record_id:
            return jsonify({"error": "ID is required"}), 400

        # Prepare the fields to update
        fields = {key: value for key, value in data.items() if
                  key in ['pre_requsite', 'summary', 'actions', 'test_data', 'acceptance_criteria'] and key != 'id'}

        # Return an error if no fields are provided to update
        if not fields:
            return jsonify({"error": "At least one field to update is required"}), 400

        # Construct the SQL query
        set_clause = ', '.join(f"{column} = %s" for column in fields)
        query = f"UPDATE `tcg`.`story_details` SET {set_clause} WHERE id = %s"

        # Prepare the values for the placeholders in the SQL query
        values = list(fields.values()) + [record_id]
        print(query)
        print(values)
        execute_query_with_values(query, values)

    return JSONResponse(content={"message": "Story updated"}, status_code=200)


@app.post("/update_qna")
async def update_qna(input_data: dict,
                     user: TokenData = Depends(get_current_user)):
    username = user.username
    # testcase_id = input_data['test_case_id']
    # accepted_status = input_data['accepted']
    roles = user.roles
    if 2 in roles:
        data = input_data

        # Extract the ID and check if it's provided
        record_id = data.get("id")
        if not record_id:
            return jsonify({"error": "ID is required"}), 400

        # Prepare the fields to update
        fields = {key: value for key, value in data.items() if key in ['query', 'context', 'answer'] and key != 'id'}

        # Return an error if no fields are provided to update
        if not fields:
            return jsonify({"error": "At least one field to update is required"}), 400

        # Construct the SQL query
        set_clause = ', '.join(f"{column} = %s" for column in fields)
        query = f"UPDATE `tcg`.`qna` SET {set_clause} WHERE id = %s"

        # Prepare the values for the placeholders in the SQL query
        values = list(fields.values()) + [record_id]
        print(query)
        print(values)
        execute_query_with_values(query, values)
        search_url = os.getenv("Knowledge_Addition")
        knowledge_Creater(record_id, user.token, search_url)

    return JSONResponse(content={"message": "qna updated"}, status_code=200)


@app.get("/getDashBoard/")
def get_updates(pr_id: str, user_story_ref: str, user: TokenData = Depends(get_current_user)):
    # Get the parameters from the request

    # detailed_userstory = f"""select id,pre_requsite as pre_requsite,summary as summary, actions,test_data,acceptance_criteria FROM tcg.story_details
    #                         where project_id={project_id} and userstory_id={user_story_id}"""
    # # Query the MySQL database for matching records
    # details_story = getDBRecord(detailed_userstory, True)
    # # print("result_returned", result[1]['query'])
    # # Return the result as JSON
    username = user.username
    roles = user.roles
    if 2 in roles:
        requirmentdetails = f"""SELECT 
        requirment_id,
        COALESCE(
            (SELECT detail FROM tcg.requirments WHERE id = requirment_id and userstory_id={user_story_ref} ), 
            (SELECT description FROM tcg.planning_item WHERE _id = requirment_id and userstory_id={user_story_ref})
        ) AS requirment_detail,
        count(id) as count FROM tcg.test_cases WHERE 
        project_id={pr_id} AND
       userstory_id = {user_story_ref} group by requirment_id ORDER BY requirment_id ASC"""
        # Query the MySQL database for matching records
        requirmentdetails = getDBRecord(requirmentdetails, True)
        result = [{"feature": row["requirment_detail"], "Testcase_count": row["count"]} for row in requirmentdetails]
        print(result)
        return JSONResponse(content={"message": result}, status_code=200)
    else:
        return JSONResponse(content={"message": "User is Not authorized "}, status_code=401)


@app.get("/get-idea/{idea_id}")
def get_idea_details(idea_id: int):
    # Step 1: Get initial idea
    idea_query = """
        SELECT id, executive_summary, business_objectives,status
        FROM intial_idea
        WHERE id = %s
    """
    ideas = fetch_all(idea_query, (idea_id,))
    if not ideas:
        raise HTTPException(status_code=404, detail="Idea not found")

    idea = ideas[0]
    if idea.get("status", "").strip().lower() == "completed":
        # Step 2: Get all features
        feature_query = """
            SELECT id, description, approach
            FROM feature_idea
            WHERE idea_id = %s
        """
        features = fetch_all(feature_query, (idea_id,))

        # Step 3: For each feature, get user stories
        feature_breackdown = []
        for feature in features:
            feature_id = feature["id"]
            userstory_query = """
                SELECT id,prerequesites, summary, actions, test_data, acceptance_criteria
                FROM ideated_user_story
                WHERE feature_id = %s
            """
            userstories = fetch_all(userstory_query, (feature_id,))
            feature_breackdown.append({
                "id": feature["id"],
                "core_feature": feature["description"],
                "approach": json.loads(feature["approach"] or "[]"),
                "userstory": [
                    {
                        "id": us["id"],
                        "prerequesites": json.loads(us["prerequesites"] or "[]"),
                        "summary": us["summary"],
                        "actions": json.loads(us["actions"] or "[]"),
                        "test_data": json.loads(us["test_data"] or "[]"),
                        "acceptance_criteria": json.loads(us["acceptance_criteria"] or "[]"),
                    }
                    for us in userstories
                ]
            })

        # Step 4: Construct the original JSON structure
        result_json = {
            "id": idea["id"],
            "executive_summary": idea["executive_summary"],
            "business_objectives": json.loads(idea["business_objectives"] or "[]"),
            "feature_breackdown": feature_breackdown
        }

        return result_json
    else:
        result_json = {
            "id": idea["id"],
            "status": idea["status"]

        }
        return result_json


@app.get("/ticket_list/{project_id}")
def get_tickets(project_id: int, user: TokenData = Depends(get_current_user)):
    publisher = PMFactory(user, project_id)
    tool = publisher.integration['tool']
    config = publisher.integration['additional_config']
    tool_map = {
        "jira": JiraAdapter,
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    success = tool_publisher.read(config)

    if success:
        return JSONResponse(content=success, status_code=200)
    else:
        return JSONResponse(content={"message": f"Failed to Fetch the details {tool.title()}"}, status_code=500)


@app.post("/ba_resource/")
async def upload_files(background_tasks: BackgroundTasks, user: TokenData = Depends(get_current_user),
                       text: Optional[str] = Form(None),
                       files: Optional[List[UploadFile]] = File(None)):
    username = user.username
    roles = user.roles
    print(user.token)
    print("i am here for sure")
    # logger.info("User story submitted "+input_data['user_input']+" by user "+username)
    if 5 in roles:
        if (not text or text.strip() == "") and not files:
            raise HTTPException(
                status_code=400,
                detail="At least one of 'test' or 'files' must be provided."
            )

        # results = {}
        # if files:
        #     for file in files:
        #         filename = file.filename.lower()
        #         extension = os.path.splitext(filename)[-1]
        #         content = ""
        #
        #         file_bytes = await file.read()
        #
        #         if extension == ".txt":
        #             content = file_bytes.decode(errors="ignore")
        #
        #
        #         elif extension == ".docx":
        #
        #             doc_stream = io.BytesIO(file_bytes)
        #
        #             doc = docx.Document(doc_stream)
        #
        #             text_parts = []
        #
        #             # Walk document body elements in order
        #
        #             for block in doc.element.body:
        #
        #                 if block.tag == qn('w:p'):  # Paragraph
        #
        #                     p = docx.text.paragraph.Paragraph(block, doc)
        #
        #                     if p.text.strip():
        #                         text_parts.append(p.text.strip())
        #
        #
        #                 elif block.tag == qn('w:tbl'):  # Table
        #
        #                     t = docx.table.Table(block, doc)
        #
        #                     for row in t.rows:
        #
        #                         row_text = []
        #
        #                         for cell in row.cells:
        #
        #                             cell_text = cell.text.strip()
        #
        #                             if cell_text:
        #                                 row_text.append(cell_text)
        #
        #                         if row_text:
        #                             text_parts.append(" | ".join(row_text))
        #
        #             content = "\n".join(text_parts)
        #
        #         elif extension == ".pdf":
        #
        #             pdf_stream = io.BytesIO(file_bytes)
        #
        #             doc = PyPDF2.PdfReader(pdf_stream)
        #
        #             pdf_text = []
        #
        #             for page in doc.pages:
        #
        #                 text1 = page.extract_text()
        #
        #                 if text1:
        #                     pdf_text.append(text1)
        #
        #             content = "\n".join(pdf_text)
        #
        #         elif extension == ".msg":
        #             with open("temp.msg", "wb") as f:
        #                 f.write(file_bytes)
        #             msg = extract_msg.Message("temp.msg")
        #             content = msg.body
        #             os.remove("temp.msg")
        #         elif extension == ".eml":
        #             with open("temp.eml", "wb") as f:
        #                 f.write(file_bytes)
        #
        #             with open("temp.eml", "rb") as f:
        #                 eml = BytesParser(policy=policy.default).parse(f)
        #
        #             eml_parts = []
        #
        #             # Add email metadata
        #             eml_parts.append(f"Subject: {eml['subject'] or ''}")
        #             eml_parts.append(f"From: {eml['from'] or ''}")
        #             eml_parts.append(f"To: {eml['to'] or ''}")
        #             eml_parts.append(f"Cc: {eml['cc'] or ''}")
        #
        #             # Extract body
        #             body_found = False
        #             for part in eml.walk():
        #                 content_type = part.get_content_type()
        #                 if content_type == "text/plain" and not body_found:
        #                     body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8',
        #                                                                 errors='replace')
        #                     eml_parts.append("\n--- Email Body ---\n" + body.strip())
        #                     body_found = True
        #
        #                 # Extract attachments
        #                 if part.get_filename():
        #                     attachment_name = part.get_filename()
        #                     attachment_data = part.get_payload(decode=True)
        #                     with open(attachment_name, "wb") as f:
        #                         f.write(attachment_data)
        #                     eml_parts.append(f"[Attachment saved as {attachment_name}]")
        #
        #             content = "\n".join(eml_parts)
        #             os.remove("temp.eml")
        #         else:
        #             content = f"Unsupported file type: {extension}"
        #
        #         results[file.filename] = content.strip()
        results = {}
        if files:
            for file in files:
                results[file.filename] = await extract_file_content(file)

        final_parts = []
        if text and text.strip():
            final_parts.append(f"{text.strip()}")

        if files:
            for fname, fcontent in results.items():
                final_parts.append(f"\n\n{fcontent.strip()}")
        final_extracted_text = "\n".join(final_parts)
        # return JSONResponse(content={
        #     "test_input": text,
        #     "files_content": results,
        #     "final_extracted_text": final_extracted_text
        #
        # })
        user_story_input = final_extracted_text
        print("\nExtracted content************\n", user_story_input, "\nExtracted content************\n")
        insert_idea_query = """
                                INSERT INTO tcg.intial_idea (input,status)
                                VALUES (%s,%s)
                            """
        id = execute_query_param(insert_idea_query, (
            user_story_input, "inprogress"
        ))

        background_tasks.add_task(babackground_task, user_story_input, id, user.token)

        # Return 202 response immediately
        return JSONResponse(
            content={"message": "Request accepted", "request_id": id},
            status_code=202)

    else:
        return JSONResponse(content={"message": "Request rejected"}, status_code=401)


@app.get("/fetch_products/{request_id}")
def fetch_versions(request_id: int,
                   user: TokenData = Depends(get_current_user)):
    """
    Query parameters:
      - product_id (int) : optional. If provided, returns versions for that product only.
    """
    publisher = TestCasePublisher(user, request_id)
    tool = publisher.integration['tool']
    print("Tool from API: ", tool)
    tool_map = {
        "testiny": TestinyPublisher,
        "kiwi": KiwiPublisher
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    success = tool_publisher.fetchProduct()

    return JSONResponse(
        content={"product": success},
        status_code=200)


@app.get("/fetch_versions/{request_id}/{product_id}")
def fetch_versions(request_id: int, product_id: int, user: TokenData = Depends(get_current_user)):
    """
    Query parameters:
      - product_id (int) : optional. If provided, returns versions for that product only.
    """

    publisher = TestCasePublisher(user, request_id)
    tool = publisher.integration['tool']
    print("Tool from API: ", tool)
    tool_map = {
        "testiny": TestinyPublisher,
        "kiwi": KiwiPublisher
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    success = tool_publisher.fetchVersions(product_id)
    return JSONResponse(
        content={"versions": success},
        status_code=200)


@app.get("/fetch_testplans/{request_id}/{product_id}/{version_id}")
def fetch_testplans(request_id: int, product_id: int, version_id: int, user: TokenData = Depends(get_current_user)):
    """
    Query parameters:
      - product_id (int) : required to scope test plans
      - version (string or int) : optional — can be version id or value (e.g. "1.0" or id)
    """
    publisher = TestCasePublisher(user, request_id)
    tool = publisher.integration['tool']
    print("Tool from API: ", tool)
    tool_map = {
        "testiny": TestinyPublisher,
        "kiwi": KiwiPublisher
    }

    if tool not in tool_map:
        print("Unsupported tool: ")
        return JSONResponse(content={"message": f"Unsupported tool: {tool}"}, status_code=400)

    tool_publisher = tool_map[tool](publisher)
    success = tool_publisher.fetchTestPlans(product_id, version_id)
    safe_testplans = make_json_safe(success)
    return JSONResponse(content={"testplans": safe_testplans}, status_code=200)


def make_json_safe(data):
    """
    Recursively convert XMLRPCDateTime and datetime objects to ISO strings.
    """
    if isinstance(data, dict):
        return {k: make_json_safe(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_json_safe(i) for i in data]
    elif isinstance(data, XMLRPCDateTime):
        return str(data)  # already in ISO-like format
    elif isinstance(data, datetime.datetime):
        return data.isoformat()
    else:
        return data


@app.get("/fetch_configuration/{request_id}")
def fetch_configuration(request_id: int, user: TokenData = Depends(get_current_user)):
    """
        Returns hierarchical config:
        Product -> Versions -> Test Plans -> Child Test Plans (recursive)
        """
    publisher = TestCasePublisher(user, request_id)
    tool = publisher.integration['tool']
    Additonal_Config = publisher.integration['additional_config']
    print("Tool from API:", tool)

    tool_map = {
        "testiny": TestinyPublisher,
        "kiwi": KiwiPublisher
    }

    if tool not in tool_map:
        return JSONResponse(
            content={"message": f"Unsupported tool: {tool}"},
            status_code=400
        )

    tool_publisher = tool_map[tool](publisher)

    # Step 1: Fetch all products
    products = tool_publisher.fetchProduct(Additonal_Config)
    print("Products",products)
    configuration = []

    for product in products:
        product_entry = {
            "id": product["id"],
            "name": product["name"],
            "version": []
        }

        # Step 2: Fetch versions for each product
        versions = tool_publisher.fetchVersions(product["id"])
        print("Versons", versions)
        for version in versions:
            version_entry = {
                "id": version["id"],
                "name": version["value"],
                "test_plan": []
            }

            # Step 3: Fetch test plans (recursive handling for child test plans)
            testplans = tool_publisher.fetchTestPlans(product["id"], version["id"])
            print("Test plans", testplans)
            version_entry["test_plan"] = build_testplan_hierarchy(testplans)

            product_entry["version"].append(version_entry)

        configuration.append(product_entry)

    return JSONResponse(content={"Configuration": make_json_safe(configuration)}, status_code=200)

def build_testplan_hierarchy(testplans):
        """
        Build recursive hierarchy of test plans using parent -> children relationship
        """
        # Convert testplans into dict for fast lookup
        plan_dict = {plan["id"]: {**plan, "children": []} for plan in testplans}

        root_plans = []

        for plan in testplans:
            parent_id = plan.get("parent")
            if parent_id:
                # Attach this plan as a child of its parent
                if parent_id in plan_dict:
                    plan_dict[parent_id]["children"].append(plan_dict[plan["id"]])
            else:
                # No parent → root level plan
                root_plans.append(plan_dict[plan["id"]])

        # Recursive JSON formatter
        def attach_children(plan):
            return {
                "id": plan["id"],
                "name": plan["name"],
                "child Test plan": [attach_children(child) for child in plan.get("children", [])]
            }

        return [attach_children(plan) for plan in root_plans]

    # Map children properly
#     def attach_children(plan):
#         return {
#             "id": plan["id"],
#             "name": plan["name"],
#             "child Test plan": [attach_children(child) for child in plan.get("children", [])]
#         }
#
# return [attach_children(plan) for plan in root_plans]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # app.run(debug=True)
