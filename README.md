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