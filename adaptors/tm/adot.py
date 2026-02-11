import base64
import requests
from adaptors.tm.tool_publishers import BaseToolPublisher
import json
import html
import requests
from requests.auth import HTTPBasicAuth


class AzureDevOpsPublisher(BaseToolPublisher):
    import html

    def build_ado_payload(self, test_case, steps_xml):

        # Safe extraction with defaults
        title = str(test_case.get("summary", "")).strip()
        description = str(test_case.get("description", "") or "").strip()

        # Safe priority handling
        raw_priority = test_case.get("priority", 2)
        try:
            priority = int(raw_priority)
            if priority not in [1, 2, 3, 4]:
                priority = 2  # Default to Medium if invalid
        except (TypeError, ValueError):
            priority = 2

        # Automation flag handling (supports multiple DB column names)
        is_automated = (
                test_case.get("is_automated")
                or test_case.get("tobeautomate")
                or False
        )

        automation_status = "Automated" if bool(is_automated) else "Not Automated"

        payload = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": html.escape(title)
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": html.escape(description)
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Priority",
                "value": priority
            },
            # {
            #     "op": "add",
            #     "path": "/fields/Microsoft.VSTS.TCM.AutomationStatus",
            #     "value": automation_status
            # },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.Steps",
                "value": steps_xml
            }
        ]

        return payload

    def create_test_case(self, test_case):
        base_url = self.publisher.get_integration_credential('url')
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}
        config = self.publisher.get_integration_credential('additional_config')

        project = config["project"]
        url = f"{base_url}/{project}/_apis/wit/workitems/$Test%20Case?api-version=7.0-preview.3"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json-patch+json"
        }

        steps_xml = self._format_steps(test_case)

        # payload = [
        #     {"op": "add", "path": "/fields/System.Title", "value": test_case["summary"]},
        #     {"op": "add", "path": "/fields/System.Description", "value": test_case["description"]},
        #     {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": int(test_case["priority"])},
        #     {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.AutomationStatus",
        #      "value": "Automated" if test_case["is_automated"] else "Not Automated"},
        #     {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml}
        # ]
        payload= self.build_ado_payload(test_case, steps_xml)

        response = requests.post(url, headers=headers, json=payload, auth=auth)

        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise Exception(response.text)

    # def _format_steps(self, test_case):
    #     steps = test_case["test_steps"]
    #     xml = '<steps id="0" last="{}">'.format(len(steps))
    #
    #     for index, step in enumerate(steps, start=1):
    #         xml += f"""
    #         <step id="{index}" type="ActionStep">
    #             <parameterizedString isformatted="true">{step['test_steps']}</parameterizedString>
    #             <parameterizedString isformatted="true">{step['expected_result']}</parameterizedString>
    #         </step>
    #         """
    #
    #     xml += "</steps>"
    #     return xml
    import json
    import html

    def _format_steps(self, test_case):
        raw_steps = test_case.get("test_steps")

        if not raw_steps:
            return '<steps id="0" last="0"></steps>'

        # If steps are stored as JSON string in DB → parse them
        if isinstance(raw_steps, str):
            try:
                steps = json.loads(raw_steps)
            except json.JSONDecodeError:
                # If not JSON, treat whole content as single step
                steps = [{
                    "test_steps": raw_steps,
                    "expected_result": test_case.get("expected_result", "")
                }]
        else:
            steps = raw_steps

        if not isinstance(steps, list):
            return '<steps id="0" last="0"></steps>'

        xml = f'<steps id="0" last="{len(steps)}">'

        for index, step in enumerate(steps, start=1):
            action = html.escape(str(step.get("test_steps", "")))
            expected = html.escape(str(step.get("expected_result", "")))

            xml += f"""
            <step id="{index}" type="ActionStep">
                <parameterizedString isformatted="true">{action}</parameterizedString>
                <parameterizedString isformatted="true">{expected}</parameterizedString>
            </step>
            """

        xml += "</steps>"
        return xml

    def link_test_case_to_user_story(self, user_story_id, test_case_id):

        base_url = self.publisher.get_integration_credential('url')
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        config = self.publisher.get_integration_credential('additional_config')

        project = config["project"]
        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}
        url = f"{base_url}/{project}/_apis/wit/workitems/{test_case_id}?api-version=7.0"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json-patch+json"
        }
        # https: // dev.azure.com / ashwanis0547 / Demo % 20
        # Project / _apis / wit / workItems / 1
        payload = [
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": "Microsoft.VSTS.Common.TestedBy-Forward",
                        "url": f"{base_url}/{project}/_apis/wit/workItems/1",
                        "attributes": {
                            "comment": "Linking test case to user story"
                        }
                    }
                }
            ]

        response = requests.patch(url, headers=headers, json=payload,auth=auth)

        if response.status_code in [200, 201]:
                return response.json()
        else:
                raise Exception(response.text)

###### This is now working - I am able to fetch All the test plan is desired formate ######
    def fetch_test_plans(self):

        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        base_url = self.publisher.get_integration_credential('url')
        config=self.publisher.get_integration_credential('additional_config')

        project = config["project"]
        url = f"{base_url}/{project}/_apis/testplan/plans?api-version=7.0"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers,auth=auth)

        print("plans:", response.json())
        if response.status_code == 200:
            plans = response.json().get("value", [])
            print("plans:",plans)

            filtered_plans = [
                {
                    "id": plan.get("id"),
                    "name": plan.get("name")
                }
                for plan in plans
            ]

            return {
                "count": len(filtered_plans),
                "plans": filtered_plans
            }
            # return response.json()
        else:
            raise Exception(response.text)

###### This is now working - I am able to fetch All the test Suites is desired formate ######
    def fetch_test_suites(self, planid:str):

        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        base_url = self.publisher.get_integration_credential('url')
        config = self.publisher.get_integration_credential('additional_config')

        project = config["project"]

        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}
        url = f"{base_url}/{project}/_apis/testplan/Plans/{planid}/suites?api-version=7.0"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json"
        }

        # response = requests.get(base_url, headers=headers, auth=auth)

        response = requests.get(url, headers=headers,auth=auth)

        if response.status_code == 200:
            data = response.json().get("value", [])

            # Step 1: Build dictionary of all suites
            suites_dict = {}

            for suite in data:
                suite_id = str(suite["id"])
                suites_dict[suite_id] = {
                    "id": suite_id,
                    "name": suite["name"],
                    "children": []
                }

            # Step 2: Build hierarchy
            root_suites = []

            for suite in data:
                suite_id = str(suite["id"])
                parent = suite.get("parentSuite")

                if parent:
                    parent_id = str(parent["id"])
                    if parent_id in suites_dict:
                        suites_dict[parent_id]["children"].append(suites_dict[suite_id])
                else:
                    root_suites.append(suites_dict[suite_id])

            return root_suites

        else:
            raise Exception(response.text)

    def add_test_case_to_suite(self, plan_id, suite_id, test_case_id):

        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        base_url = self.publisher.get_integration_credential('url')
        config = self.publisher.get_integration_credential('additional_config')

        project = config["project"]

        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}
        url = f"{base_url}/{project}/_apis/test/Plans/{plan_id}/suites/{suite_id}/testcases/{test_case_id}?api-version=7.0"
        print("url",url)
        # _apis / test / Plans / 3 / suites / 4 / testcases / 25?api - version = 7.0

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers,auth=auth)

        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise Exception(response.text)
    def create_test_plan(self, name, area_path=None, iteration=None):

        base_url = self.publisher.get_integration_credential('url')
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}
        url = f"{base_url}/_apis/wit/workitems/$Test%20Case?api-version=7.0-preview.3"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "name": name,
            "areaPath": area_path,
            "iteration": iteration
        }

        response = requests.post(url, headers=headers, json=payload,auth=auth)

        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise Exception(response.text)

    def create_test_suite(self, plan_id, name, parent_suite_id=None):

        base_url = self.publisher.get_integration_credential('url')
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}
        url = f"{base_url}/_apis/wit/workitems/$Test%20Case?api-version=7.0-preview.3"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "name": name,
            "suiteType": "staticTestSuite"
        }
        if parent_suite_id:
            payload["parentSuite"] = {"id": parent_suite_id}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in [200, 201]:
                return response.json()
        else:
                raise Exception(response.text)

    def publish(self, input_data):

        user_story_id = input_data["userstory_ref_id"]
        plan_id = input_data["plan_id"]
        suite_id = input_data["suite_id"]

        cases = self.publisher.fetch_test_cases()

        created_cases = []

        for case in cases:
            created = self.create_test_case(case)
            test_case_id = created["id"]

            # self.link_test_case_to_user_story(user_story_id, test_case_id)

            self.add_test_case_to_suite(plan_id, suite_id, test_case_id)

            created_cases.append(created)

        return created_cases

