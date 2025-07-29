from datetime import datetime
import json
import os

from pdfminer.high_level import extract_text

from app.services.llm.open_ai_service_provider import OpenAIServiceProvider
from app.services.llm.prompts.user_analysis import QUERY_ANALYSIS_PROMPT, RESUME_ANALYSIS_PROMPT


class UserAnalysisAgent:
    def __init__(self, 
                 llm_api_url: str, 
                 llm_api_key: str):
        
        self.llm_service_provider = OpenAIServiceProvider(api_url=llm_api_url, api_key=llm_api_key)


    def analyze_query(self, user_input: str,):
        """
        Analyze a natural language input from the user
        """

        prompt = QUERY_ANALYSIS_PROMPT
        messages = [{"role": "system", "content": prompt.format(curr_date= datetime.today().strftime('%Y-%m-%d'))},
                    {"role": "user", "content": user_input}]
        str_res = self.llm_service_provider.get_completion(model_name="deepseek-chat", 
                                            messages=messages, 
                                            other_prompt_args={
                                                "response_format":{
                                                    "type":"json_object"
                                                    }
                                                    })

        user_analysis_res = json.loads(str_res)

        return user_analysis_res
    
    def analyze_resume(self, user_resume_file_path: str,):
        """
        Analyze a newly uploaded resume file from the user
        """

        prompt = RESUME_ANALYSIS_PROMPT
        resume_text = extract_text(user_resume_file_path)
        messages = [{"role": "system", "content": prompt},
                    {"role": "user", "content": resume_text}]
        str_res = self.llm_service_provider.get_completion(model_name="deepseek-chat", 
                                            messages=messages, 
                                            other_prompt_args={
                                                "response_format":{
                                                        "type":"json_object"
                                                        }
                                                    })

        resume_analysis_res = json.loads(str_res)

        return resume_analysis_res