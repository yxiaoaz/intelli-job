
<br />
<div align="center">

  <h1 align="center">Intelli-Job</h1>

  <p align="center">
    An intelligent recommender system for job search
    <br />
    <a href="https://intelli-job.onrender.com/"><strong>START USING FOR FREE »</strong></a>
    <br />
  </p>
</div>

## About the Project

Intelli-Job is an intelligent job posting recommender system powered by AI. You can input your job seeking target in plain language and/or upload your resume file, and Intelli-Job will analyze your input and recommend latest job postings that serve your need.






## How to use

- **Describe your job-seek target in plain language** 
    
    Intelli-Job utilizes the power of LLM to analyze, understand, and extract key factors that constitute your ideal job posting.

    ![Alt Text](figures/demo_text_input.gif)

- **Upload your resume for qualification-based job search** 

    Intelli-Job parses and extracts crucial qualifications and skills from your resume to find opening positions that match your experience.

- **View job search results in interactive table or download as excel file**

    The interactive table supports sorting and filtering based on column values.

    You can also download the table to local machine as a .csv file.

    ![Alt Text](figures/demo_use_table.mp4)



    

## Tech Stack

- **Python 3.12+**
- **Scrapy** for web crawling
- **BeautifulSoup** for HTML parsing
- **Dash** for web interface (if used)
- **pdfminer** for PDF resume extraction
- **OpenAI/DeepSeek** for LLM-powered analysis
- **SQLAlchemy** for ORM/database
- **Redis** for caching
- **dotenv** for environment management

## Project Structure

```text
intelli_job/
├── .env
├── .gitignore
├── [init_db.py](http://_vscodecontentref_/2)
├── [main.py](http://_vscodecontentref_/3)
├── run_crawler.py
├── scrapy.cfg
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── job_matching_agent.py
│   │   ├── user_analysis_agent.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── constant.py
│   │   ├── job.py
│   │   ├── user.py
│   ├── routes/
│   └── services/
│       └── language_modeling/
│           └── prompts/
│               └── user_analysis.py
└── job_crawler/
    ├── __init__.py
    ├── items.py
    ├── [pipelines.py](http://_vscodecontentref_/11)
    ├── random_user_agent.py
    ├── settings.py
    ├── [utils.py](http://_vscodecontentref_/12)
    └── spiders/
```

## Contributing

Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. 


1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

