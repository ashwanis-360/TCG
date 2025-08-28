import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Type

import openai
import requests
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from adaptors.llm.llm_base_adaptor import BaseLLMAdapter
from adaptors.llm.llm_config import LLMConfig
from adaptors.llm.llm_openai_adaptor import OpenAIAdapter


class LLMAdapterFactory:
    """Factory to return the right LLM adapter based on config.tool."""

    @staticmethod
    def get_adapter(config: LLMConfig) -> BaseLLMAdapter:
        tool = config.tool.lower()

        if tool in ["openai", "groq", "local"]:
            return OpenAIAdapter(config)
        # elif tool == "gemini":
        #     return GeminiAdapter(config)
        # elif tool == "local":
        #     return LocalLLMAdapter(config)
        else:
            raise ValueError(f"Unsupported tool specified: {config.tool}")


def fetch_config_from_api(api_url: str, headers: Dict[str, str] = None) -> str:
    """
    Fetches config JSON from the given API URL with optional custom headers.
    """
    print(f"Fetching config from API: {api_url}")
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch config: HTTP {response.status_code} - {response.text}")
    return response.text  # JSON string


def run_llm_pipeline(config_json: str, messages: List[Dict], response_model: Type[BaseModel]) -> BaseModel | None:
    """
    The main entry point: accepts config JSON and messages, runs the selected adapter.
    """
    config_data = json.loads(config_json)
    config = LLMConfig(config_data)
    adapter = LLMAdapterFactory.get_adapter(config)
    return adapter.runpydetic(messages, response_model)


def run_llm_pipeline_text(config_json: str, messages: List[Dict]) -> str:
    """
    The main entry point: accepts config JSON and messages, runs the selected adapter.
    """
    config_data = json.loads(config_json)
    config = LLMConfig(config_data)
    adapter = LLMAdapterFactory.get_adapter(config)
    return adapter.run(messages)
