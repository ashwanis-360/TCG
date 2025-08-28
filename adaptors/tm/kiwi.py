from adaptors.tm.tool_publishers import BaseToolPublisher
import json
import requests
import ssl
import xmlrpc.client
from tcms_api import TCMS


class KiwiPublisher(BaseToolPublisher):

    # def __init__(self,cert_path=None):
    #     self.server_url = ""
    #     self.username = ""
    #     self.password = ""
    #     self.cert_path = cert_path
    #
    #     self.rpc = self._init_rpc_client()

    def _init_rpc_client(self):
        url = self.publisher.get_integration_credential('url') + "/xml-rpc/"
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
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
            # context=context
        )
        tcms = TCMS(url, username,  password)
        tcms._connection = TCMS_SERVER
        rpc = tcms.exec
        # server_proxy = xmlrpc.client.ServerProxy(url, context=context)
        # tcms = TCMS(url, username,  password)
        # tcms._connection = server_proxy
        return rpc

    def publish_test_case(self, test_case):
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
        }
        """
        formatted_case = {
            'product': 26,
            'category': 42,
            "summary": test_case['summary'],
            "priority": test_case['priority'].replace("P", ""),
            'is_automated': test_case['tobeautomate'],
            'text': "\n\n **Test Steps:**\n\n"+test_case['test_steps'].decode('utf-8')
                .replace(",", "\n")
                .replace("[", "")
                .replace("]", "")
                .replace("\"", "")+"\n\n **Expected Result:**\n\n"+test_case['expected_result'],
            'case_status':2,
            'arguments': test_case['test_data'].decode('utf-8')
                .replace("[", "")
                .replace("]", "")
                .replace("\"", ""),
            'requirement': test_case['userstory_reference'],
            'extra_link': 'http://tcg.saksoft.com:5175/testcase/'+str(test_case['id']),
            'notes': test_case['tags'].decode('utf-8')
        }
        print(formatted_case)
        return self._init_rpc_client().TestCase.create(formatted_case)

    def publish(self):
        cases = self.publisher.fetch_test_cases()
        created_cases = []
        for case in cases:
            try:
                created = self.publish_test_case(case)
                created_cases.append(created)
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
