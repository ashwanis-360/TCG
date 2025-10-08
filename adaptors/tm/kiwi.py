import os

from flask import jsonify

from adaptors.tm.tool_publishers import BaseToolPublisher
import json
import requests
import ssl
import xmlrpc.client
from tcms_api import TCMS

from common.utilities import execute_query_with_values


class KiwiPublisher(BaseToolPublisher):

    # def __init__(self,cert_path=None):
    #     self.server_url = ""
    #     self.username = ""
    #     self.password = ""
    #     self.cert_path = cert_path
    #
    #     self.rpc = self._init_rpc_client()

    def _init_rpc_client(self):
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context

        cert_path = os.getenv("KIWI_CERT_PATH", None)
        context = ssl.create_default_context(cafile=cert_path)

        url = self.publisher.get_integration_credential('url') + "/xml-rpc/"
        username = self.publisher.get_integration_credential('username')
        print(username, "****************", )
        password = self.publisher.get_integration_credential('password')
        print(username, "****************", password)
        # self.server_url = url
        # self.username = username
        # self.password = password
        # if self.cert_path:
        #     context = ssl.create_default_context(cafile=self.cert_path)
        # else:
        #     try:
        # try:
        #     _create_unverified_https_context = ssl._create_unverified_context
        # except AttributeError:
        #     # Naturally handled in older Python versions
        #     pass
        # else:
        #     ssl._create_default_https_context = _create_unverified_https_context
        # context = ssl._create_unverified_context()
        # except AttributeError:
        #     context = None
        # context = ssl.create_default_context(cafile="C:/Users/local.admin/Desktop/UNITE_SUITE/TCG/asset/kiwi-server.crt")
        TCMS_SERVER = xmlrpc.client.ServerProxy(
            url,
            context=context
        )
        tcms = TCMS(url, username, password)
        tcms._connection = TCMS_SERVER
        rpc = tcms.exec
        # server_proxy = xmlrpc.client.ServerProxy(url, context=context)
        # tcms = TCMS(url, username,  password)
        # tcms._connection = server_proxy
        return rpc

    def publish_test_case(self, test_case, product_id):
        """
        test_case should be a dictionary containing required fields:
        {
            'product': 1,
            'category': 2,
            'summary': 'Test case summary',
            'priority': 2,
            'is_automated': False,
            'text': 'Detailed steps and expected results.',
            'case_status': 1
            ########################To be added
            Product
            Version
            Test plan
            ###########################
        }
        """
        formatted_case = {
            'product': product_id,
            'category': 1,
            "summary": test_case['summary'],
            "priority": test_case['priority'].replace("P", ""),
            'is_automated': test_case['tobeautomate'],
            'text': "\n\n **Test Steps:**\n\n" + test_case['test_steps'].decode('utf-8')
            .replace(",", "\n")
            .replace("[", "")
            .replace("]", "")
            .replace("\"", "") + "\n\n **Expected Result:**\n\n" + test_case['expected_result'],
            'case_status': 2,
            'arguments': test_case['test_data'].decode('utf-8')
            .replace("[", "")
            .replace("]", "")
            .replace("\"", ""),
            'requirement': test_case['userstory_reference'],
            'extra_link': 'http://tcg.saksoft.com:5175/testcase/' + str(test_case['id']),
            'notes': test_case['tags'].decode('utf-8')
        }
        print(formatted_case)

        return self._init_rpc_client().TestCase.create(formatted_case)

    def _get_version(self, inputPayload):
        global version_obj
        payload = inputPayload
        version_data = payload.get("version", {})
        if "id" in version_data:  # Case 1 or 2
            version_id = version_data["id"]
            version_obj = self._init_rpc_client().Version.filter({"id": version_id})[0]
            return version_id
        elif "value" in version_data:  # Case 3
            version_obj = self._init_rpc_client().Version.create({
                "product": payload.get("product"),
                "value": version_data["value"]
            })
            return version_obj["id"]
        else:
            return jsonify({"error": "Invalid version info"}), 400

    def _get_Testplan(self, inputPayload):
        global Plan_obj

        payload = inputPayload
        plan_data = payload.get("test_plan", {})
        version_id = self._get_version(inputPayload)
        if "id" in plan_data:  # Case 1
            plan_id = plan_data["id"]
            test_plan_obj = self._init_rpc_client().TestPlan.filter({"id": plan_id})[0]
            return plan_id
        elif "name" in plan_data:  # Case 2 or 3
            test_plan_obj = self._init_rpc_client().TestPlan.create({
                "name": plan_data["name"],
                "type": 1,
                "product": payload.get("product"),
                "product_version": version_id,
                "parent": plan_data.get("parent", None)
            })
            return test_plan_obj["id"]
        else:
            return jsonify({"error": "Invalid test plan info"}), 400

    def publish(self, input_data):
        payload = input_data.get("testcases", [])
        print("Incoming Payload:", payload)

        product_id = input_data.get("product")
        version_data = input_data.get("version", {})
        plan_data = input_data.get("test_plan", {})
        testcase_ids = input_data.get("testcases", [])
        Plan_id = self._get_Testplan(input_data)
        cases = self.publisher.fetch_test_cases()
        created_cases = []
        for case in cases:
            try:
                created = self.publish_test_case(case, product_id)
                case_id = created['id']
                self._init_rpc_client().TestPlan.add_case(Plan_id, case_id)
                created_cases.append(created)
                query = "UPDATE `tcg`.`test_cases` SET external_ref = %s WHERE id = %s"
                values = [case_id, case['id']]
                print(query)
                print(values)
                # Execute the update
                execute_query_with_values(query, values)
                print(f"✅ Created test case ID {created['id']} - {created['summary']}")
            except Exception as e:
                print(f"❌ Failed to create test case: {case.get('summary')} | Error: {str(e)}")
        return created_cases

    # def publish(self):
    #     cases = self.publisher.fetch_test_cases()
    #     if not cases:
    #         print("No test cases found.")
    #         return False
    #
    #
    #     payload = json.dumps(formatted_cases)
    #
    #     headers = {
    #         'Content-Type': 'application/json',
    #         'Accept': 'application/json',
    #         'X-Api-Key': self.publisher.get_integration_credential('password')
    #     }
    #
    #     url = self.publisher.get_integration_credential('url') + "/api/v1/testcase/bulk"
    #     print("Here is URL", url)
    #     print("Here is Header", headers)
    #     print("Here is Payload", payload)
    #     response = requests.post(url, headers=headers, data=payload)
    #
    #     print(response.text)
    #     return response.status_code == 200
    def fetchProduct(self,Data:dict):
        try:
            products = self._init_rpc_client().Product.filter({"id": Data["id"]})
            # products is a list/dict returned by tcms-api; return directly (JSON serializable)
            return products
        except Exception as e:
            return "Unable to Fetch Products"

    def fetchVersions(self, product_id):
        try:
            query = {}
            if product_id:
                # depending on Kiwi database field name, use 'product' or 'product_id'.
                # Usually the Version model has 'product' FK field referencing Product.pk
                query = {"product": int(product_id)}
            versions = self._init_rpc_client().Version.filter(query)
            return versions
        except Exception as e:
            return "Unable to Fetch Versions for Select Product"

    def fetchTestPlans(self, product_id, version):
        if not product_id:
            return "Provide Product ID"

        try:
            # Build query for TestPlan.filter
            # Example query fields: {'product': product_id, 'version': version_value}
            # If your Kiwi model uses version_id, set accordingly. If version is omitted, return all plans for product.
            query = {"product_id": int(product_id)}
            if version:
                # try to interpret version as int id first, else pass as string value
                try:
                    query["product_version_id"] = int(version)
                except ValueError:
                    query["product_version_id"] = version
            print("Here the Query to fetch the Test plan", query)
            testplans = self._init_rpc_client().TestPlan.filter(query)
            return testplans
        except Exception as e:
            return "Unable to Fetch Test plans for Select Product and Version"
