import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Type

import openai
import requests
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from adaptors.llm.llm_config import LLMConfig


class BaseLLMAdapter(ABC):
    """Abstract base class defining the adapter interface."""
    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def runpydetic(self, messages: List[Dict],response_model: Type[BaseModel]) -> BaseModel | None:
        """Execute an LLM chat completion call and return the content."""
        pass

    @abstractmethod
    def run(self, messages: List[Dict]) -> str:
        """Execute an LLM chat completion call and return the content."""
        pass
#
#
# class OpenAIAdapter(BaseLLMAdapter):
#     """Adapter for OpenAI-compatible LLMs (including Groq, Qwen, etc.)."""
#     def runpydetic(self, messages: List[Dict],response_model: Type[BaseModel]) -> BaseModel | None:
#         print(f"[OpenAIAdapter] Calling model: {self.config.llm_model} on {self.config.base_url}")
#
#         client = OpenAI(
#             api_key=self.config.api_key,
#             base_url=self.config.base_url
#         )
#
#         retries = 0
#         max_retries = 15
#         while retries < max_retries:
#             try:
#                 # Assuming `client` is already set up for Groq API call
#                 response = client.chat.completions.create(
#                     model=self.config.llm_model,  # Adjust based on the model you want to use
#                     messages=messages,
#                     response_format={"type": "json_object"}
#                 )
#                 action = response_model(**json.loads(response.choices[0].message.content))
#                 return action  # If the response is successful, return it
#             except openai.BadRequestError as e:
#                 print(f"BadRequestError encountered: {e}. Attempt {retries + 1}/{max_retries}")
#                 # Log the error or inspect the response (e.g., response['error']) for further debugging
#             except OpenAIError as e:
#                 print(f"OpenAIError encountered: {e}. Attempt {retries + 1}/{max_retries}")
#             except Exception as e:
#                 print(f"Unexpected error: {e}. Attempt {retries + 1}/{max_retries}")
#
#             retries += 1
#             if retries < max_retries:
#                 print(f"Retrying in {1} seconds...")
#                 time.sleep(1)  # Wait for the specified delay before retrying
#             else:
#                 print("Max retries reached. No valid response obtained.")
#         return None
#
#     def run(self, messages: List[Dict]) -> str:
#         print(f"[OpenAIAdapter] Calling model: {self.config.llm_model} on {self.config.base_url}")
#
#         client = OpenAI(
#             api_key=self.config.api_key,
#             base_url=self.config.base_url
#         )
#
#         retries = 0
#         max_retries = 15
#         while retries < max_retries:
#             try:
#                 response = client.chat.completions.create(
#                     model=self.config.llm_model,
#                     messages=messages
#                 )
#                 print(f"[OpenAIAdapter] Successful response.")
#                 return response.choices[0].message.content.strip()
#             except OpenAIError as e:
#                 print(f"[OpenAIAdapter] OpenAIError: {e} (attempt {retries+1}/{max_retries})")
#             except Exception as e:
#                 print(f"[OpenAIAdapter] Unexpected error: {e} (attempt {retries+1}/{max_retries})")
#             retries += 1
#             time.sleep(1)
#         raise RuntimeError("Failed to get response from OpenAI-compatible model after retries.")
#
#
# class LLMAdapterFactory:
#     """Factory to return the right LLM adapter based on config.tool."""
#     @staticmethod
#     def get_adapter(config: LLMConfig) -> BaseLLMAdapter:
#         tool = config.tool.lower()
#
#         if tool in ["openai", "groq","local"]:
#             return OpenAIAdapter(config)
#         # elif tool == "gemini":
#         #     return GeminiAdapter(config)
#         # elif tool == "local":
#         #     return LocalLLMAdapter(config)
#         else:
#             raise ValueError(f"Unsupported tool specified: {config.tool}")
#
# def fetch_config_from_api(api_url: str, headers: Dict[str, str] = None) -> str:
#     """
#     Fetches config JSON from the given API URL with optional custom headers.
#     """
#     print(f"Fetching config from API: {api_url}")
#     response = requests.get(api_url, headers=headers)
#     if response.status_code != 200:
#         raise RuntimeError(f"Failed to fetch config: HTTP {response.status_code} - {response.text}")
#     return response.text  # JSON string
#
# def run_llm_pipeline(config_json: str, messages: List[Dict], response_model: Type[BaseModel]) -> BaseModel | None:
#     """
#     The main entry point: accepts config JSON and messages, runs the selected adapter.
#     """
#     config_data = json.loads(config_json)
#     config = LLMConfig(config_data)
#     adapter = LLMAdapterFactory.get_adapter(config)
#     return adapter.runpydetic(messages,response_model)
#
# def run_llm_pipeline_text(config_json: str, messages: List[Dict]) -> str:
#     """
#     The main entry point: accepts config JSON and messages, runs the selected adapter.
#     """
#     config_data = json.loads(config_json)
#     config = LLMConfig(config_data)
#     adapter = LLMAdapterFactory.get_adapter(config)
#     return adapter.run(messages)