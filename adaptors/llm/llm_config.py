import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Type

import openai
import requests
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

class LLMConfig:
    """Holds configuration details fetched from your API."""
    def __init__(self, config_data: Dict):
        self.project_id = config_data.get("project_id")
        self.type = config_data.get("type")
        self.url = config_data.get("url")
        self.enabled = config_data.get("enabled", False)
        self.username = config_data.get("username")
        self.password = config_data.get("password")
        self.tool = config_data.get("tool")
        self.llm_model = config_data.get("llm_model")
        self.api_key = config_data.get("password")  # assuming password is API key
        self.base_url = config_data.get("url")      # assuming URL is the API endpoint
