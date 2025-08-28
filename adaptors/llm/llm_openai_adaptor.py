import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Type

import openai
import requests
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from adaptors.llm.llm_base_adaptor import BaseLLMAdapter
from json_repair import repair_json

class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI-compatible LLMs (including Groq, Qwen, etc.)."""

    def runpydetic(self, messages: List[Dict], response_model: Type[BaseModel]) -> BaseModel | None:
        print(f"[OpenAIAdapter] Calling model: {self.config.llm_model} on {self.config.base_url}")

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )

        retries = 0
        max_retries = 15
        while retries < max_retries:
            try:
                # Assuming `client` is already set up for Groq API call
                response = client.chat.completions.create(
                    model=self.config.llm_model,  # Adjust based on the model you want to use
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.4
                )
                print(response.choices[0].message.content)
                good_json_string = repair_json(response.choices[0].message.content)
                action = response_model(**json.loads(good_json_string))
                return action  # If the response is successful, return it
            except openai.BadRequestError as e:
                print(f"BadRequestError encountered: {e}. Attempt {retries + 1}/{max_retries}")
                # Log the error or inspect the response (e.g., response['error']) for further debugging
            except OpenAIError as e:
                print(f"OpenAIError encountered: {e}. Attempt {retries + 1}/{max_retries}")
            except Exception as e:
                print(f"Unexpected error: {e}. Attempt {retries + 1}/{max_retries}")

            retries += 1
            if retries < max_retries:
                print(f"Retrying in {10} seconds...")
                time.sleep(10)  # Wait for the specified delay before retrying
            else:
                print("Max retries reached. No valid response obtained.")
        return None

    def run(self, messages: List[Dict]) -> str:
        print(f"[OpenAIAdapter] Calling model: {self.config.llm_model} on {self.config.base_url}")

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )

        retries = 0
        max_retries = 15
        while retries < max_retries:
            try:
                response = client.chat.completions.create(
                    model=self.config.llm_model,
                    messages=messages
                )
                print(f"[OpenAIAdapter] Successful response.")
                return response.choices[0].message.content.strip()
            except OpenAIError as e:
                print(f"[OpenAIAdapter] OpenAIError: {e} (attempt {retries + 1}/{max_retries})")
            except Exception as e:
                print(f"[OpenAIAdapter] Unexpected error: {e} (attempt {retries + 1}/{max_retries})")
            retries += 1
            time.sleep(10)
        raise RuntimeError("Failed to get response from OpenAI-compatible model after retries.")
