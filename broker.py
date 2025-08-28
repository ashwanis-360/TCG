import os

import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify
import json


from agents.requirmentanalyser.Feature_Analyser import requirment_spliter
from agents.querymaster.Query_Master import insert_query, gapAnalyser, knowledge_Extrator, assumption_maker
from agents.brdanalyser.brdtester import BRDAutomationPipeline
from common.LLMPublisher import fetch_config_from_api
from common.Notification import MailUtility, generate_email_template, generate_email_template_error

from agents.storybuilder.story_builder import building_story
from agents.testcasesdesigner.test_designer import test_designer
from common.utilities import getDBRecord, execute_query_param

app = Flask(__name__)

# Initialize the data array
update = []


# Index route to render the HTML page
@app.route('/')
def index():
    return render_template('index.html')
def run_stage_1(config_json, pr_id, user_story_ref, token, search_url,is_knowledge):
    updatestorystageStatus(user_story_ref, 1, None)
    updatestoryStatus(user_story_ref, "in-progress", None)
    try:
        print("********Start Stage 1**********")
        insert_query(pr_id, user_story_ref, gapAnalyser(config_json, pr_id, user_story_ref))
        if is_knowledge == "true":
            knowledge_Extrator(pr_id, user_story_ref, token, search_url)
        assumption_maker(config_json, pr_id, user_story_ref)
        print("********End Stage 1**********")
    except Exception as e:
        updatestoryStatus(user_story_ref, "Error", e)
        raise


def run_stage_2(config_json, user_story_ref):
    updatestorystageStatus(user_story_ref, 2, None)
    updatestoryStatus(user_story_ref, "in-progress", None)
    try:
        print("********Start Stage 2**********")
        building_story(config_json, user_story_ref)
        print("********End Stage 2**********")
    except Exception as e:
        updatestoryStatus(user_story_ref, "Error", e)
        raise

def run_stage_3(config_json, user_story_ref):
    updatestorystageStatus(user_story_ref, 3, None)
    updatestoryStatus(user_story_ref, "in-progress", None)
    try:
        print("********Start Stage 3**********")
        requirment_spliter(config_json, user_story_ref)
        print("********End Stage 3**********")
    except Exception as e:
        updatestoryStatus(user_story_ref, "Error", e)
        raise
def run_stage_4(config_json, user_story_ref):
    updatestorystageStatus(user_story_ref, 4, None)
    updatestoryStatus(user_story_ref, "in-progress", None)
    try:
        print("********Start Stage 4**********")
        test_designer(user_story_ref, config_json)
        updatestoryStatus(user_story_ref, "Completed", None)
        print("********End Stage 4**********")
    except Exception as e:
        updatestoryStatus(user_story_ref, "Error", e)
        raise
def background_task(user_story_ref, pr_id, token):
    # chat_history = [get_system_prompt(request.json['pr_id'])]
    load_dotenv()
    is_knowledge = os.getenv("USE_LOCAL_KNOWLEDGE_BASE")
    model = os.getenv("MODEL")
    base_url = os.getenv("BASE_URL")
    auth_url = os.getenv("AUTH_URL")
    search_url = os.getenv("SEARCH_URL")
    print(token)

    api_url = auth_url + "/api/integrations/project/"+pr_id+"/LLM"
    bearer_token = token
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    # 1) Fetch the config JSON from your API
    config_json = fetch_config_from_api(api_url, headers=headers)
    print(config_json)
    # url = auth_url+"/api/admin/llm-key"
    # headers = {
    #     "Authorization": f"Bearer {token}"
    # }
    # api_key = requests.get(url, headers=headers)
    #
    # llmk = api_key.json()
    # autopilot1 = request['autopilot']
    autopilot1 = True
    user_story_detail = f"""SELECT autopilot FROM tcg.userstory where _id={user_story_ref} and project_id={pr_id}"""
    storydetail = getDBRecord(user_story_detail, False)
    autopilot = storydetail["autopilot"]
    # autopilot = False
    if autopilot:
        print("Coming here")
        try:
            run_stage_1(config_json, pr_id, user_story_ref, token, search_url, is_knowledge)
            # pr_id = pr_id
            # print("********Start Stage 1**********")
            # updatestorystageStatus(user_story_ref, 1, None)
            # insert_query(pr_id, user_story_ref, gapAnalyser(config_json, pr_id,
            #                                                 user_story_ref))
            # print("********End Stage 1**********")
            #
            # print("********Start Stage 2**********")
            # if is_knowledge == "true":
            #     knowledge_Extrator(pr_id, user_story_ref, token,search_url)
            # assumption_maker(config_json,pr_id, user_story_ref)
            # updatestorystageStatus(user_story_ref, 2, None)
            # print("********End Stage 2**********")
            # print("********Start Stage 3**********")
            run_stage_2(config_json, user_story_ref)
            # building_story(config_json, user_story_ref)
            # updatestorystageStatus(user_story_ref, 3, None)
            # print("********End Stage 3**********")
            # print("********Start Stage 4**********")
            # requirment_spliter(config_json,user_story_ref)
            run_stage_3(config_json, user_story_ref)
            # print("********End Stage 4**********")
            # print("********Start Stage 5**********")
            # updatestorystageStatus(user_story_ref, 4, None)
            # test_designer(user_story_ref, config_json)
            run_stage_4(config_json, user_story_ref)
            # print("********End Stage 5**********")
            # print("********Update Completion**********")
            # updatestoryStatus(user_story_ref, "Completed", None)
            print("******************End of Tasks******************")
            try:
                user_story_detail = f"""SELECT reference_key,detail FROM tcg.userstory where _id={user_story_ref}"""
                storydetail = getDBRecord(user_story_detail, False)
                test_cases = f"""SELECT 
                                    requirment_id,
                                    COALESCE(
                                        (SELECT detail FROM tcg.requirments WHERE id = requirment_id and userstory_id={user_story_ref} ), 
                                        (SELECT description FROM tcg.planning_item WHERE _id = requirment_id and userstory_id={user_story_ref})
                                    ) AS requirment_detail,
                                    count(id) as count FROM tcg.test_cases WHERE 
                                    project_id={pr_id} AND
                                   userstory_id = {user_story_ref} group by requirment_id ORDER BY requirment_id ASC"""

                test_cases_list = getDBRecord(test_cases, True)
                df = pd.DataFrame(test_cases_list)
                email_body = generate_email_template("User", df, "http://tcg.saksoft.com:5175/", storydetail['detail'])
                mail_utility = MailUtility()
                subject = f'''Test Cases and Traceability Chart for completed user story : {"User Story-" + user_story_ref if storydetail['reference_key'] is None else storydetail['reference_key']}'''
                body = email_body
                # attachment = "C:/UNITE_SUITE/TCG/Project_repo/info.txt"

                mail_utility.send_email(subject, body)
            except Exception as e:
                print("Error in sending the email", e)
        except Exception as e:
            print("***************\n", e, "***************\n")
            # updatestoryStatus(user_story_ref, "Error", e)
            # updatestorystageStatus(user_story_ref, "Error", None)
            # try:
            #     user_story_detail = f"""SELECT reference_key,detail FROM tcg.userstory where _id={user_story_ref}"""
            #     storydetail = getDBRecord(user_story_detail, False)
            #     test_cases = f"""SELECT
            #                         requirment_id,
            #                         COALESCE(
            #                             (SELECT detail FROM tcg.requirments WHERE id = requirment_id and userstory_id={user_story_ref} ),
            #                             (SELECT description FROM tcg.planning_item WHERE _id = requirment_id and userstory_id={user_story_ref})
            #                         ) AS requirment_detail,
            #                         count(id) as count FROM tcg.test_cases WHERE
            #                         project_id={pr_id} AND
            #                        userstory_id = {user_story_ref} group by requirment_id ORDER BY requirment_id ASC"""
            #
            #     test_cases_list = getDBRecord(test_cases, True)
            #     df = pd.DataFrame(test_cases_list)
            #     email_body = generate_email_template_error("User", df, "http://tcg.saksoft.com:5175/",
            #                                                storydetail['detail'])
            #     mail_utility = MailUtility()
            #     subject = f'''Some error occurred during Test Cases and Traceability Generation for user story : {"User Story-" + user_story_ref if storydetail['reference_key'] is None else storydetail['reference_key']}'''
            #     body = email_body
            #
            #     mail_utility.send_email(subject, body)
            # except Exception as e:
            #     print("Error in sending the email", e)
    else:
        print("Coming here")
        try:

            # pr_id = pr_id
            # print("********Start Stage 1**********")
            # updatestorystageStatus(user_story_ref, 1, None)
            # insert_query(pr_id, user_story_ref, gapAnalyser(config_json, pr_id,
            #                                                 user_story_ref))
            # print("********End Stage 1**********")
            #
            # print("********Start Stage 2**********")
            # if is_knowledge == "true":
            #     knowledge_Extrator(pr_id, user_story_ref, token,search_url)
            # assumption_maker(config_json,pr_id, user_story_ref)
            run_stage_1(config_json, pr_id, user_story_ref, token, search_url, is_knowledge)
            updatestoryStatus(user_story_ref, "Hold", None)

        except Exception as e:
            print("***************\n", e, "***************\n")
            # updatestoryStatus(user_story_ref, "Error", e)


def deletestag_data(current_stage,user_story_ref):
    queries = []

    if current_stage == 1:
        queries = [
            ("DELETE FROM `tcg`.`qna` WHERE `userstory_id` = %s", (user_story_ref,))
        ]

    elif current_stage == 2:
        queries = [
            ("DELETE FROM `tcg`.`story_details` WHERE `userstory_id` = %s", (user_story_ref,))
        ]

    elif current_stage == 3:
        queries = [
            ("DELETE FROM `tcg`.`requirments` WHERE `userstory_id` = %s", (user_story_ref,))
        ]

    elif current_stage == 4:
        queries = [
            ("DELETE FROM `tcg`.`test_cases` WHERE `userstory_id` = %s", (user_story_ref,)),
            ("DELETE FROM `tcg`.`planning_item` WHERE `story_id` = %s", (user_story_ref,))
        ]

    else:
        print(f"[WARN] Invalid stage number: {current_stage}")
        return

    for query, params in queries:
        execute_query_param(query, params)

    print("Data Deletion done from the System by the System")


def resume_task(user_story_ref,token):
    # # chat_history = [get_system_prompt(request.json['pr_id'])]
    load_dotenv()
    is_knowledge = os.getenv("USE_LOCAL_KNOWLEDGE_BASE")
    # model = os.getenv("MODEL")
    # base_url = os.getenv("BASE_URL")
    auth_url = os.getenv("AUTH_URL")
    search_url = os.getenv("SEARCH_URL")
    print(token)
    user_story_detail = f"""
                SELECT autopilot, status, stage,project_id 
                FROM tcg.userstory 
                WHERE _id={user_story_ref}
            """
    storydetail = getDBRecord(user_story_detail, False)
    pr_id = storydetail["project_id"]
    autopilot = storydetail["autopilot"]
    status = storydetail["status"]
    current_stage = int(storydetail["stage"])

    api_url = auth_url + "/api/integrations/project/"+str(pr_id)+"/LLM"
    bearer_token = token

    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    # 1) Fetch the config JSON from your API
    config_json = fetch_config_from_api(api_url, headers=headers)
    # print(config_json)
    # # Check the Auto pilot.
    # # Then Check the Over All Status
    # # Then Read the Stage
    # user_story_detail = f"""SELECT autopilot,status,stage FROM tcg.userstory where _id={user_story_ref} and project_id={pr_id}"""
    # storydetail = getDBRecord(user_story_detail, False)

    stage_functions = [
        lambda: run_stage_1(config_json, pr_id, user_story_ref, token, search_url,is_knowledge),
        lambda: run_stage_2(config_json, user_story_ref),
        lambda: run_stage_3(config_json, user_story_ref),
        lambda: run_stage_4(config_json, user_story_ref)
    ]
    if autopilot:
        if status != "Completed":
            deletestag_data(current_stage,user_story_ref)
            for stage_num in range(current_stage-1, 3):  # from current stage to stage 4
                stage_functions[stage_num]()  # call respective stage

    # if storydetail["autopilot"]:
    #     if storydetail["status"]!="Completed":
    #         #Delete the data for that Stage
    #         #Try all the Subsequent Stages
    else:
    # Then Check the Over All Status
        if status == "Error":
            deletestag_data(current_stage,user_story_ref)
            stage_functions[current_stage-1]()
            updatestoryStatus(user_story_ref, "Hold", None)
            # updatestoryStatus(user_story_ref, "Hold", None)
        if status == "Hold":
            new_stage = current_stage + 1
            if new_stage <= 4:
                # updatestorystageStatus(user_story_ref, new_stage, None)
                stage_functions[new_stage - 1]()
                if(new_stage<4):
                    updatestoryStatus(user_story_ref, "Hold", None)# index = stage - 1
    # autopilot1 = True
    # if autopilot1:
    #     try:
    #         pr_id = pr_id
    #         print("********Start Stage 1**********")
    #         updatestorystageStatus(user_story_ref, 1, None)
    #         insert_query(pr_id, user_story_ref, gapAnalyser(config_json, pr_id,
    #                                                         user_story_ref))
    #         print("********End Stage 1**********")
    #
    #         print("********Start Stage 2**********")
    #         if is_knowledge == "true":
    #             knowledge_Extrator(pr_id, user_story_ref, token,search_url)
    #         assumption_maker(config_json,pr_id, user_story_ref)
    #         updatestorystageStatus(user_story_ref, 2, None)
    #         print("********End Stage 2**********")
    #         print("********Start Stage 3**********")
    #         building_story(config_json, user_story_ref)
    #         updatestorystageStatus(user_story_ref, 3, None)
    #         print("********End Stage 3**********")
    #         print("********Start Stage 4**********")
    #         requirment_spliter(config_json,user_story_ref)
    #
    #         print("********End Stage 4**********")
    #         print("********Start Stage 5**********")
    #         updatestorystageStatus(user_story_ref, 4, None)
    #         test_designer(user_story_ref, config_json)
    #         print("********End Stage 5**********")
    #         print("********Update Completion**********")
    #         updatestoryStatus(user_story_ref, "Completed", None)
    #         print("******************End of Tasks******************")
    #         try:
    #             user_story_detail = f"""SELECT reference_key,detail FROM tcg.userstory where _id={user_story_ref}"""
    #             storydetail = getDBRecord(user_story_detail, False)
    #             test_cases = f"""SELECT
    #                                 requirment_id,
    #                                 COALESCE(
    #                                     (SELECT detail FROM tcg.requirments WHERE id = requirment_id and userstory_id={user_story_ref} ),
    #                                     (SELECT description FROM tcg.planning_item WHERE _id = requirment_id and userstory_id={user_story_ref})
    #                                 ) AS requirment_detail,
    #                                 count(id) as count FROM tcg.test_cases WHERE
    #                                 project_id={pr_id} AND
    #                                userstory_id = {user_story_ref} group by requirment_id ORDER BY requirment_id ASC"""
    #
    #             test_cases_list = getDBRecord(test_cases, True)
    #             df = pd.DataFrame(test_cases_list)
    #             email_body = generate_email_template("User", df, "http://tcg.saksoft.com:5175/", storydetail['detail'])
    #             mail_utility = MailUtility()
    #             subject = f'''Test Cases and Traceability Chart for completed user story : {"User Story-" + user_story_ref if storydetail['reference_key'] is None else storydetail['reference_key']}'''
    #             body = email_body
    #             # attachment = "C:/UNITE_SUITE/TCG/Project_repo/info.txt"
    #
    #             mail_utility.send_email(subject, body)
    #         except Exception as e:
    #             print("Error in sending the email", e)
    #     except Exception as e:
    #         print("***************\n", e, "***************\n")
    #         updatestoryStatus(user_story_ref, "Error", e)
    #         updatestorystageStatus(user_story_ref, "Error", None)
    #         try:
    #             user_story_detail = f"""SELECT reference_key,detail FROM tcg.userstory where _id={user_story_ref}"""
    #             storydetail = getDBRecord(user_story_detail, False)
    #             test_cases = f"""SELECT
    #                                 requirment_id,
    #                                 COALESCE(
    #                                     (SELECT detail FROM tcg.requirments WHERE id = requirment_id and userstory_id={user_story_ref} ),
    #                                     (SELECT description FROM tcg.planning_item WHERE _id = requirment_id and userstory_id={user_story_ref})
    #                                 ) AS requirment_detail,
    #                                 count(id) as count FROM tcg.test_cases WHERE
    #                                 project_id={pr_id} AND
    #                                userstory_id = {user_story_ref} group by requirment_id ORDER BY requirment_id ASC"""
    #
    #             test_cases_list = getDBRecord(test_cases, True)
    #             df = pd.DataFrame(test_cases_list)
    #             email_body = generate_email_template_error("User", df, "http://tcg.saksoft.com:5175/",
    #                                                        storydetail['detail'])
    #             mail_utility = MailUtility()
    #             subject = f'''Some error occurred during Test Cases and Traceability Generation for user story : {"User Story-" + user_story_ref if storydetail['reference_key'] is None else storydetail['reference_key']}'''
    #             body = email_body
    #
    #             mail_utility.send_email(subject, body)
    #         except Exception as e:
    #             print("Error in sending the email", e)
    # else:
    #     try:
    #         pr_id = pr_id
    #         print("********Start Stage 1**********")
    #         updatestorystageStatus(user_story_ref, 1, None)
    #         insert_query(pr_id, user_story_ref, gapAnalyser(config_json, pr_id,
    #                                                         user_story_ref))
    #         print("********End Stage 1**********")
    #
    #         print("********Start Stage 2**********")
    #         if is_knowledge == "true":
    #             knowledge_Extrator(pr_id, user_story_ref, token,search_url)
    #         assumption_maker(config_json,pr_id, user_story_ref)

        # except Exception as e:
        #     print("***************\n", e, "***************\n")
        #     updatestoryStatus(user_story_ref, "Error", e)

def babackground_task(request, user_story_ref, token):
    load_dotenv()
    is_knowledge = os.getenv("USE_LOCAL_KNOWLEDGE_BASE")
    model = os.getenv("MODEL")
    base_url = os.getenv("BASE_URL")
    auth_url = os.getenv("AUTH_URL")
    search_url = os.getenv("SEARCH_URL")
    print(token)

    api_url = auth_url + "/api/integrations/project/2/LLM"
    bearer_token = token

    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    # 1) Fetch the config JSON from your API
    config_json = fetch_config_from_api(api_url, headers=headers)
    try:
        pipeline = BRDAutomationPipeline(config=config_json,transcript=request,id=user_story_ref)
        pipeline.run_pipeline()
    except Exception as e:
        print("Something went wrong", e)




def updatestoryStatus(user_story_ref, current_status, exception):
    if exception is None:
        exception = "No exception provided"

        # Sanitize the exception to make sure it is a string and handle any quotes
    exception1 = str(exception).replace('"', '\\"').replace("'", "\\'")  # Escape any quotes
    # querydata = f"""select status from `tcg`.`userstory`  WHERE `_id`={user_story_ref}"""
    # storystatus = getDBRecord(querydata, False)
    # status = storystatus["status"]
    # if status!="Error":
    querydata = f"""UPDATE `tcg`.`userstory` SET `status` = "{current_status}",`Error_details` = "{exception1}" WHERE `_id`={user_story_ref}"""

    execute_query_param(querydata)
def updatestorystageStatus(user_story_ref, current_status, exception):
    if exception is None:
        exception = "No exception provided"

        # Sanitize the exception to make sure it is a string and handle any quotes
    exception1 = str(exception).replace('"', '\\"').replace("'", "\\'")  # Escape any quotes

    querydata = f"""UPDATE `tcg`.`userstory` SET `stage` = "{current_status}" WHERE `_id`={user_story_ref}"""

    execute_query_param(querydata)

#
# # Get update method to return the latest data
# @app.route('/get_update', methods=['GET'])
# def get_update():
#     return jsonify(update)

#
# def analyze_requirements_with_techniques(json_data, pr_id, user_story_ref, key):
#     stage = 5
#     prompt = None
#     stage_name = None
#     result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#     if result:
#         stage_name = result['name']
#         prompt = result['prompt']
#     prompt = prompt.replace("{json_data}", json.dumps(json_data, indent=2))
#     prompt = prompt + (". Response should strictly follow the Json structure provided to get it parsed as Json. Do not "
#                        "include any formatting symbols like /n or /r.")
#     user_input = prompt
#     chat_history = [{"role": "user", "content": user_input}]
#     ## Before Chat
#     # list_data_str = json.dumps(chat_history).replace('"', '\\"').replace(r'\\"', r'\"')
#     log_id = before_comm_logging(chat_history, pr_id, user_story_ref, stage)
#     response, json_structure_data = send_chat_completion_request(chat_history, key)
#     ## After_Chat ## Com Log
#     chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#     after_comm_logging(log_id, chat_history)
#     # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#     #
#     ## Stage output
#     # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#     latest_response = log_stage_output(pr_id, user_story_ref, stage, json_structure_data)
#     return response.choices[0].message.content, json_structure_data


# def process_stage(pr_id, stage, chat_history, request_detail, user_story_ref, key):
#     # Fetch stage details from the database
#     result = getDBRecord(f"SELECT * FROM tcg.stage WHERE stage_index={stage}")
#     if not result:
#         return
#     stage_name = result['name']
#     prompt = result['prompt']
#     print("checkpoint 1")
#     user_input = request_detail
#     prompt = prompt.replace('{user_input}', user_input)
#     prompt = prompt + ("Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                        "include any formatting symbols like /n or /r.")
#     chat_history.append({"role": "user", "content": prompt})
#     print("checkpoint 2")
#     log_id = before_comm_logging(chat_history, pr_id, user_story_ref, stage)
#     print("checkpoint 3")
#     complete_response, json_structure_data = send_chat_completion_request(chat_history, key)
#     print("checkpoint 4")
#     chat_history.append({"role": "assistant", "content": complete_response.choices[0].message.content})
#     print("checkpoint 5")
#     after_comm_logging(log_id, chat_history)
#     latest_response = log_stage_output(pr_id, user_story_ref, stage, json_structure_data)
#     # latest_response = execute_query(
#     #     f"""INSERT INTO `tcg`.`stage_output`(`project_id`,`userstory_id`,`stage`,`output`)
#     #     VALUES({pr_id}, {user_story_ref}, {stage}, "{encode_data(json_structure_data)}");"""
#     # )
#
#     # Fetch the output data from the stage_output table
#     result = getDBRecord(f"""SELECT `output` FROM `tcg`.`stage_output` WHERE id={latest_response}""")
#
#     # Insert the questions into the qna table
#     new_record_ids = []
#     for data in json_structure_data["queries"]:
#         query_value = data["query"]
#         why_value = data["why"]
#         qid = execute_query_param(
#             f"""INSERT INTO `tcg`.`qna`(`project_id`, `userstory_id`, `query`, `context`)
#             VALUES({pr_id}, {user_story_ref}, "{query_value}", "{why_value}")"""
#         )
#         new_record_ids.append(qid)
#     try:
#         html_table = generate_query_table(result['output'])
#     except Exception:
#         html_table = "<p>Error in Table Geneartion</p>"
#     # Update the response
#     update.append({"stage_name": stage_name, "id": 1, "response": html_table})
#     return user_input, json_structure_data, user_story_ref, chat_history


# def process_stage_2(pr_id, user_input, userstory_ref, chat_history, json_structure_data, key):
#     stage = 2
#     prompt = None
#     stage_name = None
#     result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#     if result:
#         stage_name = result['name']
#         prompt = result['prompt']
#     prompt = prompt.replace('{user_input}', user_input)
#     prompt = prompt + ("Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                        "include any formatting symbols like /n or /r.")
#     ### Get the Queries and Context grom DB
#     ## SELECT query, context FROM tcg.qna where project_id=2 and userstory_id=112 and answer is not null;
#     results = getDBRecord(
#         f"""SELECT query, context FROM tcg.qna where project_id={pr_id}  and userstory_id={userstory_ref} and answer is null""",
#         True)
#     queries_json = {
#         "queries": [
#             {"query": row['query'], "why": row['context']} for row in results
#         ]
#     }
#
#     # Convert to a JSON string (pretty-printed)
#     queries_json_string = json.dumps(queries_json)
#
#     prompt = prompt.replace('{list_queries}', queries_json_string)
#
#     user_input = prompt
#     chat_history.pop(2)
#     chat_history.append({"role": "user", "content": user_input})
#     # list_data_str = json.dumps(chat_history).replace('"', '\\"').replace(r'\\"', r'\"')
#     log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#     complete_response, json_structure_data = send_chat_completion_request(chat_history, key)
#
#     chat_history.append({"role": "assistant", "content": complete_response.choices[0].message.content})
#     after_comm_logging(log_id, chat_history)
#     # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{encode_chat_hostory(chat_history)}" where id = {log_id};""")
#     # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#     log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#     # latest_response = execute_query(
#     #     f"""INSERT INTO `tcg`.`stage_output`(`project_id`,`userstory_id`,`stage`,`output`) VALUES({pr_id},{userstory_ref},{stage},"{encode_data(json_structure_data)}");""")
#
#     for query in json_structure_data["queries"]:
#         execute_query_param(
#             f"""UPDATE tcg.qna SET answer= "{query['assumption']}",knowledge_exist=0 where project_id={pr_id} and userstory_id={userstory_ref} and query="{query["query"]}" and context="{query["why"]}" order by id asc""")
#
#     try:
#         html_table = genrate_asumption_table(json.dumps(json_structure_data))
#     except Exception:
#         html_table = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 2, "response": html_table})
#     print("************* After Stage 2 ******************/n", chat_history, "*******************************/n")
#     return user_input, json_structure_data, userstory_ref, chat_history
#

# def process_stage_3(pr_id, userstory_ref, chat_history, key):
#     stage = 3
#     prompt = None
#     stage_name = None
#     result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#     if result:
#         stage_name = result['name']
#         prompt = result['prompt']
#     prompt = prompt + ("Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                        "include any formatting symbols like /n or /r.")
#     user_input = prompt
#
#     # Fetch the Chat History from DB and Then Update
#     results = getDBRecord(
#         f"""SELECT query, context,answer FROM tcg.qna where project_id={pr_id}  and userstory_id={userstory_ref}""",
#         True)
#     queries_json = {
#         "queries": [
#             {"query": row['query'], "why": row['context'], "assumption": row['answer']} for row in results
#         ]
#     }
#
#     chat_history = [get_system_prompt(pr_id),
#                     {"role": "assistant", "content": json.dumps(queries_json)},
#                     {"role": "user", "content": user_input}]
#     print("chat History for Stage 3", chat_history)
#     # list_data_str = json.dumps(chat_history).replace('"', '\\"').replace(r'\\"', r'\"')
#     log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#     ## insert the Com log
#     complete_response, json_structure_data = send_chat_completion_request(chat_history, key)
#     # Update the Stage 3 Chat History
#     chat_history.append({"role": "assistant", "content": complete_response.choices[0].message.content})
#     after_comm_logging(log_id, chat_history)
#     # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#     ## Store the user Story detailsin structure data
#     log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#     newdata = json.loads(json.dumps(json_structure_data))
#     # pre_requiste = newdata['userstory']['prerequisites'].replace('"', '\\"').replace(r'\\"', r'\"')
#     # summary = newdata['userstory']['userstorydetails'].replace('"', '\\"').replace(r'\\"', r'\"')
#     # actions = [action.replace('"', "'") for action in newdata['userstory']['actions']]
#     # test_data = [test_data.replace('"', "'") for test_data in newdata['userstory']['testdatarequired']]
#     # acceptance_criteria = [acceptance_criteria.replace('"', "'") for acceptance_criteria in
#     #                        newdata['userstory']['acceptancecriteria']]
#     print("\n*****************************")
#     print(newdata)
#     print("\n*****************************")
#     pre_requiste = newdata['userstory']['prerequisites']
#     summary = newdata['userstory']['userstorydetails']
#     actions = newdata['userstory']['actions']
#     test_data = newdata['userstory']['testdatarequired']
#     acceptance_criteria = newdata['userstory']['acceptancecriteria']
#     print("\n******************")
#     print(actions, "\n******************")
#     print(test_data, "\n******************")
#     print(acceptance_criteria, "\n******************")
#     encoded_actions = json.dumps(json.dumps(actions))
#     encoded_test_data = json.dumps(json.dumps(test_data))
#     encoded_acceptance_criteria = json.dumps(json.dumps(acceptance_criteria))
#     print("\n******************")
#     print(encoded_actions, "\n******************")
#     print(encoded_test_data, "\n******************")
#     print(encoded_test_data, "\n******************")
#
#     # test_data =newdata['userstory']['testdatarequired'].replace('"', '\\"').replace(r'\\"', r'\"')
#     # acceptance_criteria =newdata['userstory']['acceptancecriteria'].replace('"', '\\"').replace(r'\\"', r'\"')
#     try:
#         latest_response = execute_query_param(
#
#             f"""INSERT INTO `tcg`.`story_details`(`project_id`,`userstory_id`,`pre_requsite`,`summary`,`actions`,`test_data`,`acceptance_criteria`)
#             VALUES({pr_id},{userstory_ref},"{pre_requiste}","{summary}",{encoded_actions},{encoded_test_data},{encoded_acceptance_criteria});""")
#
#     except Exception as e:
#
#         latest_response = execute_query_param(
#
#             f"""INSERT INTO `tcg`.`story_details`(`project_id`,`userstory_id`,`pre_requsite`,`summary`,`actions`,`test_data`,`acceptance_criteria`)
#                     VALUES({pr_id},{userstory_ref},"{json.dumps(json.dumps(pre_requiste))}","{summary}",{encoded_actions},{encoded_test_data},{encoded_acceptance_criteria});""")
#
#     ## Stage Data update
#     # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#     # Insert the output Json Data : Project,Requirement ID,Stage, Data - Stage output
#     latest_response = execute_query_param(
#         f"""INSERT INTO `tcg`.`stage_output`(`project_id`,`userstory_id`,`stage`,`output`) VALUES({pr_id},{userstory_ref},{stage},"{encode_data(json_structure_data)}");""")
#     # Fetch the data from DB though API and pass below
#     try:
#         html_table = generate_userstory_ui(json_structure_data)
#     except Exception:
#         html_table = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 3, "response": html_table})
#     print("************* After Stage 3 ******************/n", chat_history, "*******************************/n")
#     return userstory_ref, chat_history
#
#
# def process_stage_4(pr_id, userstory_ref, chat_history, key):
#     stage = 4
#     prompt = None
#     stage_name = None
#     result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#     if result:
#         stage_name = result['name']
#         prompt = result['prompt']
#     prompt = prompt + ("Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                        "include any formatting symbols like /n or /r.")
#     user_input = prompt
#
#     chat_history.pop(2)
#     chat_history.append({"role": "user", "content": user_input})
#
#     print("Chat History for the Stage 4", chat_history)
#
#     log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#     # log_id = execute_query(
#     #     f"""INSERT INTO `tcg`.`com_log`(`project_id`, `userstory_id`, `stage`, `before_chat`, `after_chat`)VALUES( {pr_id}, {userstory_ref}, {stage}, "{list_data_str}", null);""")
#
#     response, json_structure_data = send_chat_completion_request(chat_history, key)
#     chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#     after_comm_logging(log_id, chat_history)
#     # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#     data1 = response.choices[0].message.content
#     # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#     # latest_response = execute_query(
#     #     f"""INSERT INTO `tcg`.`stage_output`(`project_id`,`userstory_id`,`stage`,`output`) VALUES({pr_id},{userstory_ref},"{stage}","{esxappeddata}");""")
#     # # Insert_Requirements
#     for data in json_structure_data['requirements']:
#         # testdata=[testdata for testdata in json.dumps(data['testdata'])]
#         # stepstotest=[stepstotest for stepstotest in json.dumps(data['stepstotest'])]
#         if data['testdata'] == "N/A":
#             testdata = "null"
#         else:
#             testdata = json.dumps(json.dumps(data['testdata']))
#         stepstotest = json.dumps(json.dumps(data['stepstotest']))
#         qid = execute_query_param(
#             f"""INSERT INTO `tcg`.`requirments`(`project_id`, `userstory_id`, `detail`, `type`,`data`,`test_steps`)VALUES({pr_id},{userstory_ref},"{data['requirement_detail']}","{data['type']}",{testdata},{stepstotest});""")
#         # new_record_ids.append(qid)
#     try:
#         html_table = generate_requirment_ui(json_structure_data)
#     except Exception:
#         html_table = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 4, "response": html_table})
#     print("************* After Stage 4 ******************/n", chat_history, "*******************************/n")
#     return data1
#

# def process_stage_5(pr_id, userstory_ref, data1, chat_history, key):
#     # try:
#     #     requirments = json.loads(extract_json_from_string(data1))
#     #     data1, json_structure_data = analyze_requirements_with_techniques(requirments['requirements'], pr_id, userstory_ref,key)
#     #     chat_history.pop(3)
#     #     chat_history.pop(3)
#     #     chat_history.append({"role": "assistant", "content": data1})
#     #     print("Chat History after stage 5", chat_history)
#     #     # new_record_ids.append(qid)
#     #     for data in json_structure_data['requirements']:
#     #         if data['boundary_value_analysis']['applicable'] and len(data['boundary_value_analysis']['attributes']) > 0:
#     #             bv = 1
#     #             bv_details = json.dumps(json.dumps(data['boundary_value_analysis']['attributes']))
#     #         else:
#     #             bv = 0
#     #             bv_details = "null"
#     #         if data['equivalent_class_partitioning']['applicable'] and len(
#     #                 data['equivalent_class_partitioning']['attributes']) > 0:
#     #             ep = 1
#     #             ep_details = json.dumps(json.dumps(data['equivalent_class_partitioning']['attributes']))
#     #         else:
#     #             ep = 0
#     #             ep_details = "null"
#     #         if data['state_transition_diagram']['applicable'] and len(data['state_transition_diagram']['attributes']) > 0:
#     #             st = 1
#     #             st_details = json.dumps(json.dumps(data['state_transition_diagram']['attributes']))
#     #         else:
#     #             st = 0
#     #             st_details = "null"
#     #         if data['decision_table']['applicable'] and len(data['decision_table']['attributes']) > 0:
#     #             dt = 1
#     #             dt_details = json.dumps(json.dumps(data['decision_table']['attributes']))
#     #         else:
#     #             dt = 0
#     #             dt_details = "null"
#     #         if data['use_case_testing']['applicable'] and len(data['use_case_testing']['attributes']) > 0:
#     #             uc = 1
#     #             uc_details = json.dumps(json.dumps(data['use_case_testing']['attributes']))
#     #         else:
#     #             uc = 0
#     #             uc_details = "null"
#     #
#     #         if data['testdata'] == "N/A":
#     #             testdata = "null"
#     #         else:
#     #             testdata = json.dumps(json.dumps(data['testdata']))
#     #         # testdata = json.dumps(json.dumps(data['testdata']))
#     #         stepstotest = json.dumps(json.dumps(data['stepstotest']))
#     #
#     #         querydata = f"""UPDATE `tcg`.`requirments` SET `bv` = {bv},`bv_details`={bv_details},`ep` = {ep},`ep_details` = {ep_details},`st` = {st},`st_details` = {st_details},`dt` = {dt},`dt_details` = {dt_details},`uc` = {uc},`uc_details` = {uc_details}
#     #                 WHERE
#     #                 (`detail`="{data['requirement_detail']}" and `type`= "{data['type']}" and `data`= {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#     #
#     #         execute_query_param(querydata)
#     #         # new_record_ids.append(qid)
#     #     try:
#     #         html_table = generate_requirment_matrix(data1)
#     #     except Exception:
#     #         html_table = "<p>Error in Table Geneartion</p>"
#     #     update.append({"stage_name": "Analysing Test Case Writing Applicability", "id": 5, "response": html_table})
#     #     print("************* After Stage 5 ******************/n", chat_history, "*******************************/n")
#     #     return data1, chat_history
#     # except Exception:
#     #     print("************* After Stage 5 ******************/n Some Json Error Occured*******************************/n")
#     print("************* After Stage 5 ******************/n Do Nothing *******************************/n")
#     return None


# def bvtest_Case(pr_id, userstory_ref, data1, key):
#     requirmentdetails = json.loads(extract_json_from_string(data1))
#     testcaseallrequirment = ""
#     stage_name = None
#     for req in requirmentdetails['requirements']:
#         if req.get("boundary_value_analysis", {}).get("applicable", None) == True:
#             stage = 6
#             prompt = None
#             result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#             if result:
#                 stage_name = result['name']
#                 prompt = result['prompt']
#             prompt = prompt.replace("{req}", json.dumps(req, indent=2))
#             prompt = prompt + (
#                 "Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                 "include any formatting symbols like /n or /r.")
#             user_input = prompt
#             user_input = user_input.replace("{req['requirement_detail']}",
#                                             json.dumps(req['requirement_detail'], indent=2))
#
#             chat_history = [get_system_prompt(pr_id), {"role": "user", "content": user_input}]
#             # Insert Com log
#             # list_data_str = json.dumps(chat_history).replace('"', '\\"').replace(r'\\"', r'\"')
#             log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#             response, json_structure_data = send_chat_completion_request(chat_history, key)
#             chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#             # Update the Com log
#             after_comm_logging(log_id, chat_history)
#             # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#             # Insert the stage output
#             # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#             latest_response = log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#             # Insert the Test Cases
#             if req['testdata'] == "N/A":
#                 testdata = " is null"
#             else:
#                 testdata = " = " + json.dumps(json.dumps(req['testdata']))
#             # testdata = json.dumps(req['testdata'])
#             stepstotest = json.dumps(json.dumps(req['stepstotest']))
#
#             querydata = f"""Select id from tcg.requirments WHERE
#                           (`detail`="{req['requirement_detail']}" and `type`= "{req['type']}" and `data` {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#             requirment_id = getDBRecord(querydata)
#             # Get the Requirment ID from DB
#
#             correctedjson_structure_data = None
#             if isinstance(json_structure_data, list):
#                 correctedjson_structure_data = json_structure_data[0]
#             elif isinstance(json_structure_data, dict):
#                 correctedjson_structure_data = json_structure_data
#             for testcase in correctedjson_structure_data['testcases']:
#                 try:
#                     test_summary = testcase['testcase_summary']
#                     test_steps = json.dumps(json.dumps(testcase['test_steps']))
#                     expected_result = testcase['expected_result']
#                     test_data = json.dumps(json.dumps(testcase['test_data']))
#                     insert_query = f"""INSERT INTO `tcg`.`test_cases`(`project_id`,`userstory_id`,`requirment_id`,`technique`,`summary`,`test_steps`,`expected_result`,`test_data`)
#                        VALUES
#                        ({pr_id},{userstory_ref},{requirment_id['id']},"Boundary Value Analysis","{test_summary}",{test_steps},"{expected_result}",{test_data});"""
#                     print("**********************\n", insert_query, "**********************\n")
#                     test_case_id = execute_query_param(insert_query)
#                 except Exception as e:
#                     print("Error in inserting this Test Cases due to Some Key error")
#
#                 # User story Ref
#                 # Project_id Ref
#             # response = client.chat.completions.create(model="llama3-70b-8192", messages=chat_history, max_tokens=8191,
#             #                                           temperature=1.2)
#             try:
#                 testcaseallrequirment = testcaseallrequirment + testcase_template(response.choices[0].message.content)
#             except Exception:
#                 testcaseallrequirment = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 6, "response": testcaseallrequirment})
#     return requirmentdetails
#
#
# def eptest_cases(pr_id, userstory_ref, requirmentdetails, key):
#     testcaseallrequirment = ""
#     stage_name = None
#     for req in requirmentdetails['requirements']:
#         if req.get("equivalent_class_partitioning", {}).get("applicable", None) == True:
#             stage = 7
#             prompt = None
#             stage_name = None
#             result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#             if result:
#                 stage_name = result['name']
#                 prompt = result['prompt']
#             prompt = prompt.replace("{req}", json.dumps(req, indent=2))
#             prompt = prompt + (
#                 "Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                 "include any formatting symbols like /n or /r.")
#             user_input = prompt
#
#             user_input = user_input.replace("{req['requirement_detail']}",
#                                             json.dumps(req['requirement_detail'], indent=2))
#
#             # Append the user input to the chat history
#
#             chat_history = [get_system_prompt(pr_id), {"role": "user", "content": user_input}]
#             # Insert Com log
#             log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#             response, json_structure_data = send_chat_completion_request(chat_history, key)
#             chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#             # Update the Com log
#             after_comm_logging(log_id, chat_history)
#             # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#             # Insert the stage output
#             # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#             latest_response = log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#             # Insert the Test Cases
#             if req['testdata'] == "N/A":
#                 testdata = " is null"
#             else:
#                 testdata = " = " + json.dumps(json.dumps(req['testdata']))
#             # testdata = json.dumps(req['testdata']).replace('"', '\\"').replace(r'\\"', r'\"')
#             stepstotest = json.dumps(json.dumps(req['stepstotest']))
#
#             querydata = f"""Select id from tcg.requirments WHERE
#                                       (`detail`="{req['requirement_detail']}" and `type`= "{req['type']}" and `data` {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#
#             requirment_id = getDBRecord(querydata)
#             # Get the Requirment ID from DB
#             correctedjson_structure_data = None
#             if isinstance(json_structure_data, list):
#                 correctedjson_structure_data = json_structure_data[0]
#             elif isinstance(json_structure_data, dict):
#                 correctedjson_structure_data = json_structure_data
#             for testcase in correctedjson_structure_data['testcases']:
#                 try:
#                     test_summary = testcase['testcase_summary']
#                     test_steps = json.dumps(json.dumps(testcase['test_steps']))
#                     expected_result = testcase['expected_result']
#                     test_data = json.dumps(json.dumps(testcase['test_data']))
#                     insert_query = f"""INSERT INTO `tcg`.`test_cases`(`project_id`,`userstory_id`,`requirment_id`,`technique`,`summary`,`test_steps`,`expected_result`,`test_data`)
#                     VALUES
#                     ({pr_id},{userstory_ref},{requirment_id['id']},"Equivalent Class Partitioning","{test_summary}",{test_steps},"{expected_result}",{test_data});"""
#                     test_case_id = execute_query_param(insert_query)
#                 except Exception as e:
#                     print("Error in inserting this Test Cases due to Some Key error")
#                 # User story Ref
#                 # Project_id Ref
#             # response = client.chat.completions.create(model="llama3-70b-8192", messages=chat_history, max_tokens=8191,
#             #                                           temperature=1.2)
#
#             try:
#                 testcaseallrequirment = testcaseallrequirment + testcase_template(response.choices[0].message.content)
#             except Exception:
#                 testcaseallrequirment = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 7, "response": testcaseallrequirment})
#
#
# def dt_test_cases(pr_id, userstory_ref, requirmentdetails, key):
#     testcaseallrequirment = ""
#     stage_name = None
#     for req in requirmentdetails['requirements']:
#         if req.get("decision_table", {}).get("applicable", None) == True:
#             stage = 8
#             prompt = None
#             result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#             if result:
#                 stage_name = result['name']
#                 prompt = result['prompt']
#             prompt = prompt.replace("{req}", json.dumps(req, indent=2))
#             prompt = prompt + (
#                 "Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                 "include any formatting symbols like /n or /r.")
#             user_input = prompt
#             user_input = user_input.replace("{req['requirement_detail']}",
#                                             json.dumps(req['requirement_detail'], indent=2))
#             # Append the user input to the chat history
#             chat_history = [get_system_prompt(pr_id), {"role": "user", "content": user_input}]
#             # Insert Com log
#             log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#             response, json_structure_data = send_chat_completion_request(chat_history, key)
#             chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#             # Update the Com log
#             after_comm_logging(log_id, chat_history)
#             # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#             # Insert the stage output
#             # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#             latest_response = log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#             # Insert the Test Cases
#             if req['testdata'] == "N/A":
#                 testdata = " is null"
#             else:
#                 testdata = " = " + json.dumps(json.dumps(req['testdata']))
#             # testdata = json.dumps(req['testdata']).replace('"', '\\"').replace(r'\\"', r'\"')
#             stepstotest = json.dumps(json.dumps(req['stepstotest']))
#
#             querydata = f"""Select id from tcg.requirments WHERE
#                                                   (`detail`="{req['requirement_detail']}" and `type`= "{req['type']}" and `data` {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#
#             requirment_id = getDBRecord(querydata)
#             # Get the Requirment ID from DB
#
#             correctedjson_structure_data = None
#             if isinstance(json_structure_data, list):
#                 correctedjson_structure_data = json_structure_data[0]
#             elif isinstance(json_structure_data, dict):
#                 correctedjson_structure_data = json_structure_data
#             for testcase in correctedjson_structure_data['testcases']:
#                 try:
#                     test_summary = testcase['testcase_summary']
#                     test_steps = json.dumps(json.dumps(testcase['test_steps']))
#                     expected_result = testcase['expected_result']
#                     test_data = json.dumps(json.dumps(testcase['test_data']))
#                     insert_query = f"""INSERT INTO `tcg`.`test_cases`(`project_id`,`userstory_id`,`requirment_id`,`technique`,`summary`,`test_steps`,`expected_result`,`test_data`)
#                                    VALUES
#                                    ({pr_id},{userstory_ref},{requirment_id['id']},"Decision Table Testing","{test_summary}",{test_steps},"{expected_result}",{test_data});"""
#                     test_case_id = execute_query_param(insert_query)
#                 except Exception as e:
#                     print("Error in inserting this Test Cases due to Some Key error")
#
#                 # User story Ref
#                 # Project_id Ref
#             # response = client.chat.completions.create(model="llama3-70b-8192", messages=chat_history, max_tokens=8191,
#             #                                           temperature=1.2)
#
#             try:
#                 testcaseallrequirment = testcaseallrequirment + testcase_template(response.choices[0].message.content)
#             except Exception:
#                 testcaseallrequirment = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 8, "response": testcaseallrequirment})
#
#
# def st_test_cases(pr_id, userstory_ref, requirmentdetails, key):
#     testcaseallrequirment = ""
#     stage_name = None
#     for req in requirmentdetails['requirements']:
#         if req.get("state_transition_diagram", {}).get("applicable", None) == True:
#             stage = 9
#             prompt = None
#             result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#             if result:
#                 stage_name = result['name']
#                 prompt = result['prompt']
#             prompt = prompt.replace("{req}", json.dumps(req, indent=2))
#             prompt = prompt + (
#                 "Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                 "include any formatting symbols like /n or /r.")
#             user_input = prompt
#             user_input = user_input.replace("{req['requirement_detail']}",
#                                             json.dumps(req['requirement_detail'], indent=2))
#
#             # Append the user input to the chat history
#
#             chat_history = [get_system_prompt(pr_id), {"role": "user", "content": user_input}]
#             # Insert Com log
#             log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#             response, json_structure_data = send_chat_completion_request(chat_history, key)
#             chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#             # Update the Com log
#             after_comm_logging(log_id, chat_history)
#             # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#             # Insert the stage output
#             # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#             latest_response = log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#             if req['testdata'] == "N/A":
#                 testdata = " is null"
#             else:
#                 testdata = " = " + json.dumps(json.dumps(req['testdata']))
#             # testdata = json.dumps(req['testdata']).replace('"', '\\"').replace(r'\\"', r'\"')
#             stepstotest = json.dumps(json.dumps(req['stepstotest']))
#
#             querydata = f"""Select id from tcg.requirments WHERE
#                                                   (`detail`="{req['requirement_detail']}" and `type`= "{req['type']}" and `data` {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#
#             requirment_id = getDBRecord(querydata)
#             # Get the Requirment ID from DB
#
#             correctedjson_structure_data = None
#             if isinstance(json_structure_data, list):
#                 correctedjson_structure_data = json_structure_data[0]
#             elif isinstance(json_structure_data, dict):
#                 correctedjson_structure_data = json_structure_data
#             for testcase in correctedjson_structure_data['testcases']:
#                 try:
#                     test_summary = testcase['testcase_summary']
#                     test_steps = json.dumps(json.dumps(testcase['test_steps']))
#                     expected_result = testcase['expected_result']
#                     test_data = json.dumps(json.dumps(testcase['test_data']))
#                     insert_query = f"""INSERT INTO `tcg`.`test_cases`(`project_id`,`userstory_id`,`requirment_id`,`technique`,`summary`,`test_steps`,`expected_result`,`test_data`)
#                                    VALUES
#                                    ({pr_id},{userstory_ref},{requirment_id['id']},"State Transitioning","{test_summary}",{test_steps},"{expected_result}",{test_data});"""
#                     test_case_id = execute_query_param(insert_query)
#                 except Exception as e:
#                     print("Error in inserting this Test Cases due to Some Key error")
#
#                 # User story Ref
#                 # Project_id Ref
#             # response = client.chat.completions.create(model="llama3-70b-8192", messages=chat_history, max_tokens=8191,
#             #                                           temperature=1.2)
#
#             try:
#                 testcaseallrequirment = testcaseallrequirment + testcase_template(response.choices[0].message.content)
#             except Exception:
#                 testcaseallrequirment = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 9, "response": testcaseallrequirment})
#
#
# def uc_test_cases(pr_id, userstory_ref, requirmentdetails, key):
#     testcaseallrequirment = ""
#     stage_name = None
#     for req in requirmentdetails['requirements']:
#         if req.get("use_case_testing", {}).get("applicable", None) == True:
#             stage = 10
#             prompt = None
#
#             result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#             if result:
#                 stage_name = result['name']
#                 prompt = result['prompt']
#             prompt = prompt.replace("{req}", json.dumps(req, indent=2))
#             prompt = prompt + (
#                 "Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                 "include any formatting symbols like /n or /r.")
#             user_input = prompt
#             user_input = user_input.replace("{req['requirement_detail']}",
#                                             json.dumps(req['requirement_detail'], indent=2))
#
#             # Append the user input to the chat history
#             chat_history = [get_system_prompt(pr_id), {"role": "user", "content": user_input}]
#             # Insert Com log
#             log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#             response, json_structure_data = send_chat_completion_request(chat_history, key)
#             chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#             # Update the Com log
#             after_comm_logging(log_id, chat_history)
#             # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#             # Insert the stage output
#             # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#             latest_response = log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#             # Insert the Test Cases
#             if req['testdata'] == "N/A":
#                 testdata = " is null"
#             else:
#                 testdata = " = " + json.dumps(json.dumps(req['testdata']))
#             # testdata = json.dumps(req['testdata']).replace('"', '\\"').replace(r'\\"', r'\"')
#             stepstotest = json.dumps(json.dumps(req['stepstotest']))
#
#             querydata = f"""Select id from tcg.requirments WHERE
#                                                   (`detail`="{req['requirement_detail']}" and `type`= "{req['type']}" and `data` {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#
#             requirment_id = getDBRecord(querydata)
#             # Get the Requirment ID from DB
#
#             correctedjson_structure_data = None
#             if isinstance(json_structure_data, list):
#                 correctedjson_structure_data = json_structure_data[0]
#             elif isinstance(json_structure_data, dict):
#                 correctedjson_structure_data = json_structure_data
#             for testcase in correctedjson_structure_data['testcases']:
#                 try:
#                     test_summary = testcase['testcase_summary']
#                     test_steps = json.dumps(json.dumps(testcase['test_steps']))
#                     expected_result = testcase['expected_result']
#                     test_data = json.dumps(json.dumps(testcase['test_data']))
#                     insert_query = f"""INSERT INTO `tcg`.`test_cases`(`project_id`,`userstory_id`,`requirment_id`,`technique`,`summary`,`test_steps`,`expected_result`,`test_data`)
#                                    VALUES
#                                    ({pr_id},{userstory_ref},{requirment_id['id']},"Use Case Testing","{test_summary}",{test_steps},"{expected_result}",{test_data});"""
#                     test_case_id = execute_query_param(insert_query)
#                 except Exception as e:
#                     print("Error in inserting this Test Cases due to Some Key error")
#
#                 # User story Ref
#                 # Project_id Ref
#             # response = client.chat.completions.create(model="llama3-70b-8192", messages=chat_history, max_tokens=8191,
#             #                                           temperature=1.2)
#
#             try:
#                 testcaseallrequirment = testcaseallrequirment + testcase_template(response.choices[0].message.content)
#             except Exception:
#                 testcaseallrequirment = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 10, "response": testcaseallrequirment})


# def generic_test_cases(pr_id, userstory_ref, requirmentdetails, key):
#     testcaseallrequirment = ""
#     stage_name = None
#     for req in requirmentdetails['requirements']:
#         if not (
#                 req.get('boundary_value_analysis', {}).get('applicable', None) == True or
#                 req.get('equivalent_class_partitioning', {}).get('applicable', None) == True or
#                 req.get('state_transition_diagram', {}).get('applicable', None) == True or
#                 req.get('decision_table', {}).get('applicable', None) == True or
#                 req.get('use_case_testing', {}).get('applicable', None) == True
#         ):
#             stage = 11
#             prompt = None
#
#             result = getDBRecord(f"""SELECT * FROM tcg.stage where stage_index={stage}""")
#             if result:
#                 stage_name = result['name']
#                 prompt = result['prompt']
#             prompt = prompt.replace("{req}", json.dumps(req, indent=2))
#             prompt = prompt + (
#                 "Response should follow the Json structure provided strictly to get it parsed as Json. Do not "
#                 "include any formatting symbols like /n or /r.")
#             user_input = prompt
#             user_input = user_input.replace("{req['requirement_detail']}",
#                                             json.dumps(req['requirement_detail'], indent=2))
#
#             # Append the user input to the chat history
#             chat_history = [get_system_prompt(pr_id), {"role": "user", "content": user_input}]
#             # Insert Com log
#             log_id = before_comm_logging(chat_history, pr_id, userstory_ref, stage)
#             response, json_structure_data = send_chat_completion_request(chat_history, key)
#             chat_history.append({"role": "assistant", "content": response.choices[0].message.content})
#             # Update the Com log
#             after_comm_logging(log_id, chat_history)
#             # execute_query(f"""UPDATE `tcg`.`com_log` SET `after_chat` = "{list_data_str}" where id = {log_id};""")
#
#             # Insert the stage output
#             # esxappeddata = json.dumps(json_structure_data).replace('"', '\\"').replace(r'\\"', r'\"')
#
#             latest_response = log_stage_output(pr_id, userstory_ref, stage, json_structure_data)
#             # Insert the Test Cases
#             if req['testdata'] == "N/A":
#                 testdata = " is null"
#             else:
#                 testdata = " = " + json.dumps(json.dumps(req['testdata']))
#             # testdata = json.dumps(req['testdata']).replace('"', '\\"').replace(r'\\"', r'\"')
#             stepstotest = json.dumps(json.dumps(req['stepstotest']))
#
#             querydata = f"""Select id from tcg.requirments WHERE
#                                                       (`detail`="{req['requirement_detail']}" and `type`= "{req['type']}" and `data` {testdata} and test_steps={stepstotest} and `project_id`={pr_id} and `userstory_id`={userstory_ref})"""
#
#             requirment_id = getDBRecord(querydata)
#             # Get the Requirment ID from DB
#
#             correctedjson_structure_data = None
#             if isinstance(json_structure_data, list):
#                 correctedjson_structure_data = json_structure_data[0]
#             elif isinstance(json_structure_data, dict):
#                 correctedjson_structure_data = json_structure_data
#             for testcase in correctedjson_structure_data['testcases']:
#                 try:
#                     test_summary = testcase['testcase_summary']
#                     test_steps = json.dumps(json.dumps(testcase['test_steps']))
#                     expected_result = testcase['expected_result']
#                     test_data = json.dumps(json.dumps(testcase['test_data']))
#                     insert_query = f"""INSERT INTO `tcg`.`test_cases`(`project_id`,`userstory_id`,`requirment_id`,`technique`,`summary`,`test_steps`,`expected_result`,`test_data`)
#                                        VALUES
#                                        ({pr_id},{userstory_ref},{requirment_id['id']},"Generic Test Cases","{test_summary}",{test_steps},"{expected_result}",{test_data});"""
#                     test_case_id = execute_query_param(insert_query)
#                 except Exception as e:
#                     print("Error in inserting this Test Cases due to Some Key error")
#
#             # User story Ref
#             # Project_id Ref
#         # response = client.chat.completions.create(model="llama3-70b-8192", messages=chat_history, max_tokens=8191,
#         #                                           temperature=1.2)
#
#         try:
#             testcaseallrequirment = testcaseallrequirment + testcase_template(response.choices[0].message.content)
#         except Exception:
#             testcaseallrequirment = "<p>Error in Table Geneartion</p>"
#     update.append({"stage_name": stage_name, "id": 10, "response": testcaseallrequirment})





if __name__ == '__main__':
    app.run(debug=False)
