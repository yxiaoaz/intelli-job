from typing import List, Optional
from core.models import JobListing
from services.jina_client import JinaReader
from services.firecrawl_client import Firecrawler
from core.cache_manager import CacheManager

class JobScraperAgent:
    def __init__(self, cache: CacheManager, use_jina: bool = True):
        self.cache = cache
        self.parser = JinaReader() if use_jina else Firecrawler()
        self.parser_stats = {'success': 0, 'failures': 0}

    def scrape_url(self, url: str) -> List[JobListing]:
        """Scrape using AI web scraping service"""
        try:
            # Check cache first
            if cached := self.cache.get_jobs(url):
                return cached

            # Use selected parser
            if isinstance(self.parser, JinaReader):
                result = self.parser.extract_jobs(url)
            else:
                scraped = self.parser.scrape(url)
                result = self._transform_firecrawl(scraped, url)

            # Normalize and cache
            jobs = self._normalize_jobs(result, url)
            self.cache.set_jobs(url, jobs)
            self.parser_stats['success'] += 1
            return jobs

        except Exception as e:
            self.parser_stats['failures'] += 1
            return []

    def _transform_firecrawl(self, data: dict, source_url: str) -> list:
        """Convert Firecrawl output to job listings format"""
        # Implementation depends on Firecrawl's response schema
        return [{
            'title': data.get('title'),
            'company': self._extract_company(source_url),
            'location': data.get('location', 'Remote'),
            'description': data.get('text', ''),
            'url': source_url
        }]
    
    # ... (keep existing _normalize_jobs and helper methods)