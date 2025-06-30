import os

# API Keys
JINA_API_KEY = os.getenv('JINA_API_KEY')  # From https://jina.ai/reader
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')  # From https://firecrawl.dev

# Service Selection
USE_JINA = True  # Set False to use Firecrawl instead