import json
import time
from typing import List, Dict, Type

import requests
from pydantic import BaseModel

from adaptors.llm.llm_base_adaptor import BaseLLMAdapter
from json_repair import repair_json


class ErrorResponseModel(BaseModel):
    llm_response_status: str
    error_type: str
    message: str
    retries: int


class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter for Google Gemini models
    Supports:
    - Plain text response (run)
    - Structured JSON response (runpydetic)
    """

    # -------------------------------
    # JSON / PYDANTIC MODE
    # -------------------------------
    def runpydetic(self, messages: List[Dict], response_model: Type[BaseModel]) -> BaseModel:
        print(f"[GeminiAdapter] Calling model: {self.config.llm_model}")

        retries = 0
        max_retries = 15
        last_error = None

        while retries < max_retries:
            try:
                prompt = self._convert_messages(messages, force_json=True)

                response_text = self._call_gemini(prompt)

                print(response_text)

                # Repair JSON if needed
                fixed_json = repair_json(response_text)

                return response_model(**json.loads(fixed_json))

            except Exception as e:
                print(f"[GeminiAdapter] Error: {e} (attempt {retries + 1}/{max_retries})")
                last_error = {"type": type(e).__name__, "message": str(e)}

            retries += 1
            if retries < max_retries:
                time.sleep(10)

        return ErrorResponseModel(
            llm_response_status="failed",
            error_type=last_error["type"],
            message=last_error["message"],
            retries=retries
        )

    # -------------------------------
    # PLAIN TEXT MODE
    # -------------------------------
    def run(self, messages: List[Dict]) -> str:
        print(f"[GeminiAdapter] Calling model: {self.config.llm_model}")

        retries = 0
        max_retries = 15

        while retries < max_retries:
            try:
                prompt = self._convert_messages(messages, force_json=False)

                response_text = self._call_gemini(prompt)

                print("[GeminiAdapter] Successful response.")
                return response_text.strip()

            except Exception as e:
                print(f"[GeminiAdapter] Error: {e} (attempt {retries + 1}/{max_retries})")

            retries += 1
            time.sleep(10)

        raise RuntimeError("Failed to get response from Gemini after retries.")

    # -------------------------------
    # CORE GEMINI CALL
    # -------------------------------
    def _call_gemini(self, prompt: str) -> str:
        url = f"{self.config.base_url}/{self.config.llm_model}:generateContent?key={self.config.api_key}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }

        response = requests.post(url, json=payload, timeout=60)

        if response.status_code != 200:
            raise Exception(f"Gemini API Error: {response.text}")

        data = response.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            raise Exception(f"Unexpected Gemini response: {data}")

    # -------------------------------
    # MESSAGE CONVERSION
    # -------------------------------
    def _convert_messages(self, messages: List[Dict], force_json: bool = False) -> str:
        """
        Convert OpenAI-style messages → Gemini prompt
        """

        system_parts = []
        user_parts = []
        assistant_parts = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                system_parts.append(content)
            elif role == "user":
                user_parts.append(content)
            elif role == "assistant":
                assistant_parts.append(content)

        prompt = ""

        if system_parts:
            prompt += "SYSTEM INSTRUCTIONS:\n" + "\n".join(system_parts) + "\n\n"

        if assistant_parts:
            prompt += "CONTEXT:\n" + "\n".join(assistant_parts) + "\n\n"

        if user_parts:
            prompt += "USER QUERY:\n" + "\n".join(user_parts) + "\n\n"

        # 🔥 Important for JSON mode (equivalent to response_format=json_object)
        if force_json:
            prompt += (
                "\n\nSTRICT INSTRUCTIONS:\n"
                "Return ONLY valid JSON.\n"
                "Do not add explanation, text, or formatting.\n"
                "Ensure JSON is complete and parsable."
            )

        return prompt.strip()