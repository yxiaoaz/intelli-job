from typing import Any, Dict, List
import json


from openai import OpenAI


class OpenAIServiceProvider:
    """
    Unified interface for invoking LLM models that accept the OpenAI API
    """

    def __init__(
        self,
        api_url: str = "https://api.deepseek.com",
        api_key: str = None,
    ):

        self.api_key = api_key
        self.api_url = api_url

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
        )

    def get_completion(
        self,
        model_name: str = "deepseek-chat",
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "What's 1+1 ?"},
        ],
        other_prompt_args: Dict[str, Any] = {},
    ):

        response = self.client.chat.completions.create(
            model=model_name, messages=messages, **other_prompt_args
        )

        return response.choices[0].message.content
