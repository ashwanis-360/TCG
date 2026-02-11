import requests
import base64
from typing import Dict, Any, List

from requests.auth import HTTPBasicAuth

from adaptors.pm.pm_base_adaptor import PMBaseAdapter


class AzureDevOpsAdapter(PMBaseAdapter):

    # def _get_auth_header(self):
    #     """
    #     Azure DevOps uses PAT with Basic Auth
    #     Username is empty, PAT is password
    #     """
    #     username = self.publisher.get_integration_credential('username')
    #     password = self.publisher.get_integration_credential('password')
    #     # pat = self.publisher.get_integration_credential('pat')
    #     # token = f":{pat}"
    #     encoded_token = base64.b64encode(token.encode()).decode()
    #     return {
    #         "Authorization": f"Basic {encoded_token}",
    #         "Content-Type": "application/json"
    #     }

    def read(self, query_params: dict) -> dict:
        """
        Fetch User Stories by State (similar to Jira read)
        query_params example:
        {
            "project": "Demo Project",
            "state": ["New", "Active"]
        }
        """

        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        base_url = self.publisher.get_integration_credential('url')

        project = query_params["project"]
        states = query_params["status"]

        if not isinstance(states, list):
            states = [states]

        state_list = ", ".join([f"'{s}'" for s in states])

        # WIQL Query
        wiql_query = {
            "query": f"""
                SELECT [System.Id]
                FROM WorkItems
                WHERE [System.WorkItemType] = 'User Story'
                AND [System.State] IN ({state_list})
                ORDER BY [System.ChangedDate] DESC
            """
        }

        wiql_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=7.0"

        auth = HTTPBasicAuth(username, password)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        print(f"[DEBUG] URL: {base_url}")

        print("[AzureDevOpsAdapter] Fetching work item IDs")
        response = requests.post(wiql_url, headers=headers, json=wiql_query,auth=auth)
        response.raise_for_status()

        work_items = response.json().get("workItems", [])

        if not work_items:
            return {"tickets": []}

        ids = [item["id"] for item in work_items]

        # Fetch details in batch
        batch_url = f"{base_url}/{project}/_apis/wit/workitemsbatch?api-version=7.0"

        batch_payload = {
            "ids": ids,
            "fields": [
                "System.Title",
                "System.State",
                "System.Description",
                "Microsoft.VSTS.Common.AcceptanceCriteria"
            ]
        }

        print("[AzureDevOpsAdapter] Fetching detailed work items")
        batch_response = requests.post(batch_url, headers=headers, json=batch_payload,auth=auth)
        batch_response.raise_for_status()

        detailed_items = batch_response.json().get("value", [])

        tickets = []

        for item in detailed_items:
            fields = item.get("fields", {})

            description = fields.get("System.Description", "")
            acceptance = fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")

            # Merge description + acceptance criteria (similar to Jira plain text merge)
            full_description = f"{description}\n\nAcceptance Criteria:\n{acceptance}"

            tickets.append({
                "id": str(item.get("id")),
                "key": str(item.get("id")),   # Azure doesn't have key like Jira
                "summary": fields.get("System.Title", ""),
                "description": full_description,
                "status": fields.get("System.State", "")
            })

        print(f"[AzureDevOpsAdapter] Fetched {len(tickets)} user stories")

        return {"tickets": tickets}

    def update(self, data: dict) -> dict:
        """
        Update Description of Work Item
        data:
        {
            "ticket_key": "1",
            "description": "<div>New Content</div>"
        }
        """

        organization = self.publisher.get_integration_credential('organization')
        project = self.publisher.get_integration_credential('project')
        work_item_id = data["ticket_key"]
        new_description = data["description"]

        headers = self._get_auth_header()
        headers["Content-Type"] = "application/json-patch+json"

        url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.0"

        patch_payload = [
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": new_description
            }
        ]

        print(f"[AzureDevOpsAdapter] Updating Work Item {work_item_id}")

        response = requests.patch(url, headers=headers, json=patch_payload)
        response.raise_for_status()

        return {"result": f"Work Item {work_item_id} updated successfully."}

    def create_ticket(self, data: dict) -> dict:
        """
        Create new User Story
        data:
        {
            "project_key": "Demo Project",
            "summary": "New Story",
            "description": "<div>Story details</div>"
        }
        """

        organization = self.publisher.get_integration_credential('organization')
        project = data["project_key"]

        headers = self._get_auth_header()
        headers["Content-Type"] = "application/json-patch+json"

        url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/$User%20Story?api-version=7.0"

        patch_payload = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": data["summary"]
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": data["description"]
            }
        ]

        print("[AzureDevOpsAdapter] Creating new User Story")

        response = requests.patch(url, headers=headers, json=patch_payload)
        response.raise_for_status()

        result = response.json()

        return {"result": f"Work Item created with ID {result['id']}"}
