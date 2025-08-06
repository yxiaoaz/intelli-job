from typing import Any, Dict, List, Union
import json
from pathlib import Path
import logging
import time

from openai import OpenAI

from app.config import get_project_root

logging.basicConfig(filename=os.path.join(get_project_root(), "logs", "job_crawler.log"),
                    filemode='a',
                    format='%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',)
logger = logging.getLogger(__name__)

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


    def get_embedding_batch(
        self,
        input_file_path: str,
        output_file_path: str = "output.jsonl",
        error_file_path: str = "error.jsonl",
    ) -> List[List[float]]:
        try:
            input_file_id = self._upload_file(input_file_path)
            batch_id = self._create_batch_job(input_file_id)

            status = ""
            while status not in ["completed", "failed", "expired", "cancelled"]:
                status = self._check_job_status(batch_id)
                time.sleep(10) 
           
            if status == "failed":
                batch = self._client.batches.retrieve(batch_id)
                logger.error(f"Batch job on batch id {batch_id} failed:{batch.errors}\n", exc_info=True)
                logger.info(f"参见错误码文档: https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
                return
            
    
            output_file_id = self._get_output_id(batch_id)
            if output_file_id:
                self._download_results(output_file_id, output_file_path)
            error_file_id = self._get_error_id(batch_id)
            if error_file_id:
                self._download_errors(error_file_id, error_file_path)
                logger.info(f"参见错误码文档: https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
            
            # Read the output file and return the embeddings
            with open(output_file_path, "r", encoding="utf-8") as f:
                json_list = list(f)
                res = [json.loads(line) for line in json_list]
            
            return [{'id':j['custom_id'], 'embedding': j['response']['body']['data'][0]['embedding']} for j in res]
        
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.info(f"参见错误码文档: https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
        

    def _upload_file(self, file_path):
        file_object = self.client.files.create(file=Path(file_path), purpose="batch")
        logger.info(f"File uploaded successfully, generated file id: {file_object.id}\n")
        return file_object.id

    def _create_batch_job(self, input_file_id):
        batch = self.client.batches.create(input_file_id=input_file_id, endpoint="/v1/embeddings", completion_window="24h")
        return batch.id

    def _check_job_status(self, batch_id):
        batch = self.client.batches.retrieve(batch_id=batch_id)
        return batch.status

    def _get_output_id(self, batch_id):
        batch = self.client.batches.retrieve(batch_id=batch_id)
        logger.info(f"Generated output file, id: {batch.output_file_id}\n")
        return batch.output_file_id

    def _get_error_id(self, batch_id):
        batch = self.client.batches.retrieve(batch_id=batch_id)
        return batch.error_file_id

    def _download_results(self, output_file_id, output_file_path):
        content = self.client.files.content(output_file_id)
        content.write_to_file(output_file_path)

    def _download_errors(self, error_file_id, error_file_path):
        content = self.client.files.content(error_file_id)
        content.write_to_file(error_file_path)