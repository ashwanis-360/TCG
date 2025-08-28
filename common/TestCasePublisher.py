import os
import requests
from dotenv import load_dotenv
from common.utilities import getDBRecord
# **********************Need to Rename is as factory**********************
class TestCasePublisher:
    def __init__(self, user, userstory_id):
        load_dotenv()
        self.user = user
        self.token = user.token
        self.username = user.username
        self.userstory_id = userstory_id
        self.auth_url = os.getenv("AUTH_URL")
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.project_id = self._get_project_id()
        self.integration = self._get_integration_credentials()

    def _get_project_id(self):
        query = f"SELECT project_id FROM tcg.userstory WHERE _id = {self.userstory_id}"
        return getDBRecord(query, False)['project_id']

    def _get_integration_credentials(self):
        url = f"{self.auth_url}/api/integrations/project/{self.project_id}/TM"
        response = requests.get(url, headers=self.headers)
        data = response.json()
        return {
            "tool": data['tool'].lower(),
            "url": data['url'],
            "username": data['username'],
            "password": data['password']
        }

    def fetch_test_cases(self):
        query = f"""
            SELECT 
    tc.id, 
    tc.project_id, 
    tc.summary, 
    tc.test_steps, 
    tc.expected_result, 
    tc.test_data, 
    tc.tags, 
    tc.priority, 
    tc.tobeautomate,
    COALESCE(NULLIF(us.reference_key, ''), CONCAT('USERSTORY-', tc.userstory_id)) AS userstory_reference
FROM 
    tcg.test_cases tc
JOIN 
    tcg.userstory us ON tc.userstory_id = us._id
WHERE 
    tc.userstory_id = {self.userstory_id} AND tc.accepted = true
        """
        return getDBRecord(query, True)

    def get_integration_credential(self, key: str):
        return self.integration.get(key)
