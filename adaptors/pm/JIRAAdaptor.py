import json

import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, Any

from adaptors.pm.pm_base_adaptor import PMBaseAdapter
from common.utilities import extract_text_from_adf


class JiraAdapter(PMBaseAdapter):

    def read(self, query_params: dict) -> dict:

        base_url = self.publisher.get_integration_credential('url')
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        jql = f'project = "{query_params["project"]}" AND status = "{query_params["status"]}"'
        url = f"{base_url}/rest/api/3/search"
        params = {"jql": jql}
        print(f"[JiraAdapter] Fetching issues with JQL: {jql}")
        auth = HTTPBasicAuth(username, password)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        print(url, "***", headers, "*******", params, "*******", headers, "*******", username, "*******", password)
        response = requests.get(url, headers=headers, params=params, auth=auth)
        response.raise_for_status()
        issues = response.json().get("issues", [])

        detailed_tickets = []

        # Fetch details for each ticket found
        for issue in issues:
            ticket_key = issue["key"]
            detail_url = f"{base_url}/rest/api/3/issue/{ticket_key}"
            print(f"[JiraAdapter] Fetching details for ticket: {ticket_key}")
            detail_response = requests.get(detail_url, headers=headers, auth=auth)
            detail_response.raise_for_status()
            data = detail_response.json()

            description_adf = data["fields"].get("description", "")
            plain_text = extract_text_from_adf(description_adf)
            print("Description as text:\n", plain_text)
            detailed_tickets.append({
                "id": issue["id"],
                "key": data["key"],
                "summary": data["fields"]["summary"],
                "description": plain_text,
                "status": data["fields"]["status"]["name"]
            })
        return {"tickets": detailed_tickets}

    def update(self, data: dict) -> dict:

        ticket_key = data["ticket_key"]
        current_description=data["description"]
        print("************",ticket_key,"************",current_description)
        base_url = self.publisher.get_integration_credential('url')
        print(f"[JiraAdapter] Fetching details for ticket: {ticket_key}")
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        url = f"{base_url}/rest/api/3/issue/{ticket_key}"
        # print(f"[JiraAdapter] Fetching issues with JQL: {jql}")
        auth = HTTPBasicAuth(username, password)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        data = response.json()
        ticket_current_Details={
            "key": data["key"],
            "summary": data["fields"]["summary"],
            "description": data["fields"].get("description", ""),
            "status": data["fields"]["status"]["name"]
        }
        details = json.dumps(ticket_current_Details, indent=2)
        print("Details of first ticket:", details)

        current_description_adf = json.loads(details).get("description", None)
        existing_content = current_description_adf.get("content", [])

        print("Details Adf Description:", existing_content)
        # new_content_adf = {
        #
        #     "content": current_description
        # }
        merged_content = existing_content + current_description
        # updated_content = existing_content + new_content_adf
        # existing_content.append(new_content_adf)
        updated_description_adf = {
            "version": 1,
            "type": "doc",
            "content": merged_content
        }
        # Update the ticket
        print(updated_description_adf)

        # ticket_key = data["ticket_key"]
        url = f"{base_url}/rest/api/3/issue/{ticket_key}"

        fields = {"description": updated_description_adf}

        # Directly use the ADF structure provided by the caller
        payload = {"fields": fields}

        print(f"[JiraAdapter] Updating ticket: {ticket_key}")
        # print(f"[JiraAdapter] Payload: {json.dumps(payload, indent=2)}")

        # Convert description to ADF if present
        # description_text = fields["description"]
        # if "description" in fields:
        #     description_text = fields["description"]
        #     fields["description"] = {
        #         "type": "doc",
        #         "version": 1,
        #         "content": description_text
        #     }
        #
        # payload = {"fields": description_text}
        print(f"[JiraAdapter] Updating ticket: {ticket_key}")
        print(f"[JiraAdapter] Updating ticket: {payload}")

        response = requests.put(url, headers=headers, auth=auth, json=payload)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print("[JiraAdapter] Error response:", response.status_code, response.text)
            raise e

        return {"result": f"Ticket {ticket_key} updated successfully."}

    def create_ticket(self, data: dict) -> dict:

        base_url = self.publisher.get_integration_credential('url')
        username = self.publisher.get_integration_credential('username')
        password = self.publisher.get_integration_credential('password')
        url = f"{base_url}/rest/api/3/issue"
        auth = HTTPBasicAuth(username, password)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        des = {
            "type": "doc",
            "version": 1,
            "content": data["description"]
        }

        payload = {
            "fields": {
                "project": {"key": data["project_key"]},
                "summary": data["summary"],
                "description": des,
                "issuetype": {"name": data["issue_type"]}
            }
        }
        response = requests.post(url, headers=headers, auth=auth, json=payload)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print("[JiraAdapter] Error response:", response.status_code, response.text)
            raise e

        result = response.json()
        return {"result": f"Ticket created with key {result['key']}"}
