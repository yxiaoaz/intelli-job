from typing import Any, Dict, List, Union
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
    ) -> str:

        response = self.client.chat.completions.create(
            model=model_name, messages=messages, **other_prompt_args
        )

        return response.choices[0].message.content

    def get_embedding(
        self,
        model_name: str = "text-embedding-v4",
        input_txt: Union[str, List[str]] = "吃了吗您内",
        dimensions: int = 1024, # does NOT work for any model, e.g. qwq only available with text-embedding-v3 and text-embedding-v4
    ) -> List[List[float]]:

        response = self.client.embeddings.create(
            model=model_name,
            input=input_txt,
            dimensions=dimensions,  
            encoding_format="float",
        )

        response_data = json.loads(response.model_dump_json())["data"]

        return [r["embedding"] for r in response_data]
