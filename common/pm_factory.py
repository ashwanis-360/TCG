import os
import requests
from dotenv import load_dotenv
from common.utilities import getDBRecord


# **********************Need to Rename is as factory**********************
class PMFactory:
    def __init__(self, user, projectid):
        load_dotenv()
        self.user = user
        self.token = user.token
        self.username = user.username
        self.auth_url = os.getenv("AUTH_URL")
        self.headers = {"Authorization": f"Bearer {self.token}"}

        self.project_id = projectid
        self.integration = self._get_integration_credentials()

    def _get_integration_credentials(self):
        url = f"{self.auth_url}/api/integrations/project/{self.project_id}/PM"
        response = requests.get(url, headers=self.headers)
        data = response.json()
        return {
            "tool": data['tool'].lower(),
            "url": data['url'],
            "username": data['username'],
            "password": data['password'],
            "additional_config":data['config']
        }

    def get_integration_credential(self, key: str):
        return self.integration.get(key)
