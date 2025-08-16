from datetime import datetime
import json
import os
import time

from docx import Document
from dotenv import load_dotenv
from pdfminer.high_level import extract_text


from app.config import get_project_root
from app.services.language_modeling.open_ai_service_provider import (
    OpenAIServiceProvider,
)
from app.services.language_modeling.prompts.user_analysis import (
    QUERY_ANALYSIS_PROMPT,
    RESUME_ANALYSIS_PROMPT,
)


# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))


class UserAnalysisAgent:
    def __init__(self):

        self.llm_service_provider = OpenAIServiceProvider(
            api_url=os.getenv("LLM_COMPLETION_API_URL"),
            api_key=os.getenv("LLM_COMPLETION_API_KEY"),
        )

    def analyze_query(
        self,
        user_input: str,
    ):
        """
        Analyze a natural language input from the user
        """

        prompt = QUERY_ANALYSIS_PROMPT
        messages = [
            {
                "role": "system",
                "content": prompt.format(
                    curr_date=datetime.today().strftime("%Y-%m-%d")
                ),
            },
            {"role": "user", "content": user_input},
        ]
        start = time.time()
        str_res = self.llm_service_provider.get_completion(
            model_name="deepseek-chat",
            messages=messages,
            other_prompt_args={"response_format": {"type": "json_object"}},
        )
        print(f"Took {time.time() - start} seconds to extract keywords from user query")
        user_analysis_res = json.loads(str_res)

        return user_analysis_res

    def analyze_resume(
        self,
        user_resume_file_path: str,
    ):
        """
        Analyze a newly uploaded resume file from the user
        """

        prompt = RESUME_ANALYSIS_PROMPT
        resume_text = self._extract_text(user_resume_file_path)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": resume_text},
        ]

        start = time.time()
        str_res = self.llm_service_provider.get_completion(
            model_name="deepseek-chat",
            messages=messages,
            other_prompt_args={"response_format": {"type": "json_object"}},
        )
        print(f"Took {time.time() - start} seconds to extract keywords from resume")
        resume_analysis_res = json.loads(str_res)

        return resume_analysis_res

    def _extract_text(self, user_resume_file_path: str):
        # determine the file type
        file_extension = os.path.splitext(user_resume_file_path)[-1]

        if file_extension in {".doc", ".docx"}:
            document = Document(user_resume_file_path)
            full_text = [paragraph.text for paragraph in document.paragraphs]

            return "\n".join(full_text)

        if file_extension == ".pdf":
            return extract_text(user_resume_file_path)
