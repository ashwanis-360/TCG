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
        # query_params = {"status": ["TO DO", "IN PROGRESS"], "project": "KAN"}

        statuses = query_params["status"]
        print("Dictionary coming", query_params)
        print("Extracted Status", statuses)

        # Ensure statuses is a list
        if not isinstance(statuses, list):
            statuses = [statuses]

        # Build the status list string with **escaped double quotes**
        status_list = ", ".join([f'"{s}"' for s in statuses])

        # Construct JQL
        jql = f'project = "{query_params["project"]}" AND status IN ({status_list})'
        print("Formed JQL", jql)
        # jql = f'project = "{query_params["project"]}" AND status = "{query_params["status"]}"'

        # ✅ Use standard JIRA search endpoint (not /search/jql)
        url = f"{base_url}/rest/api/3/search/jql"

        # ✅ Request fields directly to avoid separate calls per issue
        params = {
            "jql": jql,
            "fields": "id,key,summary,description,status"
        }

        print(f"[JiraAdapter] Fetching issues with JQL: {jql}")
        auth = HTTPBasicAuth(username, password)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] Params: {params}")

        # Send the API request
        response = requests.get(url, headers=headers, params=params, auth=auth)
        response.raise_for_status()
        data = response.json()

        issues = data.get("issues", [])
        detailed_tickets = []

        # ✅ Convert ADF description to text if present
        for issue in issues:
            fields = issue.get("fields", {})
            description_adf = fields.get("description", "")
            plain_text = extract_text_from_adf(description_adf)

            detailed_tickets.append({
                "id": issue.get("id"),
                "key": issue.get("key"),
                "summary": fields.get("summary", ""),
                "description": plain_text,
                "status": fields.get("status", {}).get("name", "")
            })

        print(f"[JiraAdapter] Fetched {len(detailed_tickets)} issues")
        print("[JiraAdapter] Fetched:", detailed_tickets)
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
