from adaptors.tm.tool_publishers import BaseToolPublisher
import json
import requests

class TestinyPublisher(BaseToolPublisher):

    def format_test_cases(self, raw_cases):
        formatted = []
        for case in raw_cases:
            formatted_case = {
                "title": case['summary'],
                "project_id": 1,
                "sort_index": case['id'],
                "template": "TEXT",
                "precondition_text": "",
                "content_text": case['test_data'].decode('utf-8')
                .replace(",", "\n")
                .replace("[", "")
                .replace("]", "")
                .replace("\"", ""),
                "steps_text": case['test_steps'].decode('utf-8')
                .replace(",", "\n")
                .replace("[", "")
                .replace("]", "")
                .replace("\"", ""),
                "expected_result_text": case['expected_result'],
                "priority": 1,
                "status": "READY",
                "testcase_type": "FUNCTIONAL"
            }
            formatted.append(formatted_case)
        return formatted
    def publish(self):
        cases = self.publisher.fetch_test_cases()
        if not cases:
            print("No test cases found.")
            return False

        formatted_cases = self.format_test_cases(cases)
        payload = json.dumps(formatted_cases)

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Api-Key': self.publisher.get_integration_credential('password')
        }


        url = self.publisher.get_integration_credential('url') + "/api/v1/testcase/bulk"
        print("Here is URL",url)
        print("Here is Header", headers)
        print("Here is Payload", payload)
        response = requests.post(url, headers=headers, data=payload)

        print(response.text)
        return response.status_code == 200

