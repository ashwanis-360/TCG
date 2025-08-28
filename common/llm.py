import json
import time
from typing import Type

import openai
from openai import OpenAI, OpenAIError
from pydantic import BaseModel


def get_llm_response_pydantic2(apikey: str, baseurl: str, model: str, messages1: list,
                               response_model: Type[BaseModel]) -> BaseModel | None:


    client = OpenAI(
        base_url=baseurl,
        api_key=apikey,  # required, but unused
    )
    # Enable instructor patches for Groq client
    retries = 0
    max_retries = 15
    while retries < max_retries:
        try:
            # Assuming `client` is already set up for Groq API call
            response = client.chat.completions.create(
                model=model,  # Adjust based on the model you want to use
                messages=messages1,
                response_format={"type": "json_object"}
            )
            action = response_model(**json.loads(response.choices[0].message.content))
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
            print(f"Retrying in {1} seconds...")
            time.sleep(1)  # Wait for the specified delay before retrying
        else:
            print("Max retries reached. No valid response obtained.")
    return None

def call_llm(apikey,baseurl,model,messages):

    client = openai.OpenAI(
        api_key=apikey,  # Replace with your actual Groq API key
        base_url=baseurl  # Ensure this is the correct endpoint
    )
    # Call the ChatCompletion API
    response = client.chat.completions.create(
        model=model,  # Adjust based on the model you want to use
        messages=messages
    )
    print("This is the response from LLM",response)
    return response.choices[0].message.content.strip()
