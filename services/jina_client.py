from jina import Client
from config import JINA_API_KEY
import json

class JinaReader:
    def __init__(self):
        self.client = Client(api_key=JINA_API_KEY)
    
    def extract_jobs(self, url: str) -> list[dict]:
        """Use Jina Reader API to extract structured job data"""
        response = self.client.post(
            '/v1/reader',
            json={
                'url': url,
                'reader': 'job-listing',
                'options': {
                    'extract': ['title', 'company', 'location', 'description']
                }
            }
        )
        return json.loads(response.text)['data']