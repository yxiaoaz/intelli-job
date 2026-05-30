
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

![Alt Text](figures/readme_demo.png)




## How to use

- **Describe your job-seek target in plain language** 
    
    Intelli-Job utilizes the power of LLM to analyze, understand, and extract key factors that constitute your ideal job posting.

    ![Alt Text](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ2tzd3ptdGIwOThoZXBlbG93emg0ZHV3Nng3bmhkZXVtaG8xZ3kwMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xchvkb69GAwa0eUPRC/giphy.gif)

- **Upload your resume for qualification-based job search** 

    Intelli-Job parses and extracts crucial qualifications and skills from your resume to find opening positions that match your experience.

- **View job search results in interactive table or download as excel file**

    The interactive table supports sorting and filtering based on column values.

    You can also download the table to local machine as a .csv file.

    ![Alt Text](https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExemx4OHBnMnpiODI4dGY2bTd1Mmh2NGI2OTlkbnZ0bGcycWpwbGx5diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/RuR2mC1Zu0yaiHDPNW/giphy.gif)


## Project Structure

### 🆕 New Architecture (FastAPI + Next.js)

```
intelli-job/
├── backend/              # ⭐ FastAPI Backend (NEW)
│   ├── app/
│   │   ├── api/v1/      # API Routes (auth, jobs, chat)
│   │   ├── core/agents/ # LangChain DeepAgents
│   │   ├── services/    # Business Logic Services
│   │   ├── repositories/# Data Access Layer
│   │   ├── models/      # SQLAlchemy Models
│   │   └── main.py      # FastAPI Entry Point
│   ├── requirements.txt
│   └── README.md
├── frontend/             # ⭐ Next.js Frontend (NEW)
│   ├── app/             # Next.js App Router
│   ├── components/      # React Components
│   └── package.json
└── docs/                 # 📚 Documentation
    ├── PRODUCT_DESIGN_PRD.md
    ├── CODE_FRAMEWORK.md
    └── IMPLEMENTATION_SUMMARY.md
```

### ⚠️ Legacy Architecture (Dash - Deprecated)

```
intelli-job/
├── main.py              # Dash Application (DEPRECATED)
├── app/                 # Legacy Backend Logic (DEPRECATED)
│   ├── core/
│   ├── models/
│   └── services/
└── job_crawler/         # Scrapy Spider (Still Active)
    ├── spiders/
    ├── pipelines/
    └── ...
```

**Note**: The `app/` directory and `main.py` are kept for reference only. Please use `backend/` for new development.

## Contributing

Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request.

### Quick Start

1. Fork this repo
2. Setup Backend:
   ```bash
   cd intelli-job/backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env  # Edit with your credentials
   uvicorn app.main:app --reload
   ```
3. Setup Frontend:
   ```bash
   cd intelli-job/frontend
   npm install
   npm run dev
   ```
4. Create your Feature Branch 
    ```bash
    git checkout -b feature/AmazingFeature
    ```
5. Commit your Changes 
    ```bash
    git commit -m 'Add some AmazingFeature'
    ```
6. Push to the Branch 
    ```bash
    git push origin feature/AmazingFeature
    ```
7. Open a Pull Request

