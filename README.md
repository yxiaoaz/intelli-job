

## Project Organization

```
intelli-job/
├── agents/
│   ├── __init__.py
│   ├── company_discovery.py       # Company Discovery Agent
│   ├── career_page_finder.py      # Career Page Finder Agent
│   ├── job_scraper.py             # Job Scraper Agent (main orchestrator)
│   └── llm_extractor.py           # LLM Extraction Agent
├── core/
│   ├── __init__.py
│   ├── orchestrator.py            # Main system orchestrator
│   ├── cache_manager.py           # Disk-based caching
│   ├── database.py                # SQLite database operations
│   └── models.py                  # Pydantic models
├── parsers/
│   ├── __init__.py
│   ├── heuristic.py               # Heuristic parser
│   └── known_platforms/           # Platform-specific parsers
│       ├── __init__.py
│       ├── greenhouse.py
│       ├── lever.py
│       └── workday.py
├── utils/
│   ├── __init__.py
│   ├── html_fetcher.py            # HTML downloader with caching
│   ├── html_utils.py              # HTML processing helpers
│   ├── llm_utils.py               # LLM API wrappers
│   └── logging.py                 # Custom logging setup
├── ui/
│   ├── __init__.py
│   └── streamlit_app.py           # Streamlit UI
├── tests/
│   ├── __init__.py
│   ├── test_agents.py
│   └── test_parsers.py
├── data/
│   ├── cache/                     # DiskCache storage
│   └── jobs.db                    # SQLite database
├── config.py                      # Configuration settings
├── main.py                        # CLI entry point
└── requirements.txt
```

## Development Plan
1. Start with core/models.py and config.py to set up foundations
2. Implement utils/html_fetcher.py and core/cache_manager.py
3. Build heuristic parser (parsers/heuristic.py)
4. Implement Company Discovery Agent
5. Build Career Page Finder Agent
6. Create Job Scraper Agent with parser routing
7. Add LLM Extraction Agent
8. Finally, build the Streamlit UI