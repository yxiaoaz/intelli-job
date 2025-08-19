from datetime import datetime

from dash import html, dcc
import dash_bootstrap_components as dbc


from app.models.constant import RecruitmentType, AcademicQualification
from app.services.language_modeling.utils import ACCEPTED_RESUME_FILE_EXTENSION


COLUMN_DEFS = {
    "zh": [
        {
            "headerName": "发布时间",
            "field": "update_time",
            "width": 100,
            "filter": "agDateColumnFilter",
            "filterParams": {
                "browserDatePicker": True,
                "minValidYear": 2000,
                "maxValidYear": datetime.now().year + 1,
            },
            "hide": False,  # Hidden on mobile by default
        },
        {
            "headerName": "公司",
            "field": "company",
            "filter": True,
            "flex": 1,
            "minWidth": 120,
        },
        {
            "headerName": "职位",
            "field": "title",
            "filter": True,
            "flex": 1,
            "minWidth": 120,
        },
        {
            "headerName": "地点",
            "field": "location",
            "width": 80,
            "hide": False,
        },
        {
            "headerName": "工作类型",
            "field": "recruitment_type",
            "width": 100,
            "filter": "agSetColumnFilter",
            "filterParams": {
                "values": [rc.value for rc in RecruitmentType],
                "suppressAndOrCondition": True,
            },
            "hide": False,
        },
        {
            "headerName": "薪资",
            "field": "salary",
            "width": 100,
            "filter": True,
            "hide": True,
        },
        {
            "headerName": "学历",
            "field": "education",
            "width": 80,
            "filter": "agSetColumnFilter",
            "filterParams": {
                "values": [ac.value for ac in AcademicQualification],
                "suppressAndOrCondition": True,
            },
            "hide": False,
        },
        {
            "headerName": "工作内容",
            "field": "description",
            "tooltipField": "description",
            "cellRenderer": "html",
            "wrapText": True,
            "autoHeight": True,
            "filter": False,
            "resizable": True,
            "minWidth": 150,
        },
        {
            "headerName": "链接",
            "field": "url",
            "cellRenderer": "markdown",
            "width": 80,
            "autoHeight": True,
        },
    ],
    "en": [
        {
            "headerName": "Update Time",
            "field": "update_time",
            "width": 100,
            "filter": "agDateColumnFilter",
            "filterParams": {
                "browserDatePicker": True,
                "minValidYear": 2000,
                "maxValidYear": datetime.now().year + 1,
            },
            "hide": False,  # Hidden on mobile by default
        },
        {
            "headerName": "Company",
            "field": "company",
            "filter": True,
            "flex": 1,
            "minWidth": 120,
        },
        {
            "headerName": "Position",
            "field": "title",
            "filter": True,
            "flex": 1,
            "minWidth": 120,
        },
        {
            "headerName": "地点",
            "field": "location",
            "width": 80,
            "hide": False,  # Hidden on mobile by default
        },
        {
            "headerName": "Type",
            "field": "recruitment_type",
            "width": 100,
            "filter": "agSetColumnFilter",
            "filterParams": {
                "values": [rc.value for rc in RecruitmentType],
                "suppressAndOrCondition": True,
            },
            "hide": False,  # Hidden on mobile by default
        },
        {
            "headerName": "Salary",
            "field": "salary",
            "width": 100,
            "filter": True,
            "hide": True,
        },
        {
            "headerName": "Min. Qualification",
            "field": "education",
            "width": 80,
            "filter": "agSetColumnFilter",
            "filterParams": {
                "values": [ac.value for ac in AcademicQualification],
                "suppressAndOrCondition": True,
            },
            "hide": False,  # Hidden on mobile by default
        },
        {
            "headerName": "Description",
            "field": "description",
            "tooltipField": "description",
            "cellRenderer": "html",
            "wrapText": True,
            "autoHeight": True,
            "filter": False,
            "resizable": True,
            "minWidth": 150,
        },
        {
            "headerName": "Link",
            "field": "url",
            "cellRenderer": "markdown",
            "width": 80,
            "autoHeight": True,
        },
    ],
}

TRANSLATIONS = {
    "en": {
        # App title
        "app_title": "IntelliJob - AI Job Assistant",
        # Navbar
        "navbar_brand": "IntelliJob",
        "by_text": "By: ",
        "github": "GitHub",
        "linkedin": "LinkedIn",
        # Job search card
        "job_search_target_title": "Job Search Preferences",
        "job_search_target_placeholder": "e.g. 2024 Computer Science graduate, proficient in Python and machine learning, looking for data analysis jobs in Beijing...",
        # Resume upload card
        "upload_resume_title": "Upload Resume (.pdf/.docx/.doc)",
        "upload_resume_text": html.Div(["Drag or ", html.A("upload from local")]),
        "remove_resume_text": "Drop resume",
        # Search options card
        "search_options_title": "Search Settings",
        "search_mode_label": "Search Mode:",
        "search_mode_options": [
            {"label": "Semantic Search", "value": "semantic"},
            {"label": "Keyword Search", "value": "sparse"},
            {"label": "Hybrid Search", "value": "hybrid"},
        ],
        "search_mode_tooltip": "Semantic: intelligent matching; Keyword: traditional search; Hybrid: combine both",
        "topk_label": "Number of Jobs:",
        "topk_tooltip": "Set the number of jobs to return (1-5000)",
        # Buttons
        "match_button": "Start Matching",
        "export_button": "Export to Excel",
        "reset_filters_button": "Reset Filters",
        "close_description_button": "Close",
        # Results section
        "recommended_jobs_table_title": "Recommended Jobs",
        "no_description": "No description",
        "url": "[SOURCE]({url})",
        "no_link": "No link",
        # Job table headers
        "columnDefs": COLUMN_DEFS["en"],
        # Modals
        "job_description_title": "Job Description Details",
        "full_description": "Full Description",
        # Alerts and messages
        "resume_upload_notification": "Resume uploaded: {resume_filename}",
        "resume_parsed": "Successfully parsed resume: {resume_filename}",
        "no_input_warning": "Please enter job preferences or upload a resume",
        "invalid_file_extension_warning": "Resume only supports these formats: {ACCEPTED_RESUME_FILE_EXTENSION}",
        "parse_error": "Failed to parse resume: {resume_filename}",
        "query_error": "Failed to analyze job preferences",
        "match_error": "Job matching failed",
        "toggle_job_description_hint": dcc.Markdown(
            "**Double click on `Description` to view the whole content**"
        ),
        # Recruitment types
        "recruitment_type": {
            RecruitmentType.EXPERIENCED.name: "Full Time (Experienced)",
            RecruitmentType.GRADUATE.name: "Full Time (Fresh Grad)",
            RecruitmentType.INTERN.name: "Internship",
        },
        # Education levels
        "education": {
            AcademicQualification.ALL.name: "No Requirements",
            AcademicQualification.ASSOCIATE.name: "Associate",
            AcademicQualification.UNDERGRADUATE.name: "Undergraduate",
            AcademicQualification.MASTERS.name: "Masters",
            AcademicQualification.DOCTOR.name: "Doctors",
        },
    },
    "zh": {
        # App title
        "app_title": "IntelliJob - AI求职助手",
        # Navbar
        "navbar_brand": "Intelli Job",
        "by_text": "By: ",
        "github": "GitHub",
        "linkedin": "LinkedIn",
        # Job search target input card
        "job_search_target_title": "求职意向描述",
        "job_search_target_placeholder": "例如：2024届计算机硕士，擅长Python和机器学习，想找北京的数据分析工作...",
        # Resume upload card
        "upload_resume_title": "上传简历 (.pdf/.docx/.doc)",
        "upload_resume_text": html.Div(["拖放或 ", html.A("选择文件")]),
        "remove_resume_text": "移除简历",
        # Search options card
        "search_options_title": "检索设置",
        "search_mode_label": "搜索模式:",
        "search_mode_options": [
            {"label": "语义搜索", "value": "semantic"},
            {"label": "关键词搜索", "value": "sparse"},
            {"label": "混合搜索", "value": "hybrid"},
        ],
        "search_mode_tooltip": "语义搜索：智能匹配；关键词搜索：传统检索；混合搜索：结合两者",
        "topk_label": "返回职位数:",
        "topk_tooltip": "设置返回的职位数量（1-5000）",
        # Buttons
        "match_button": "开始匹配",
        "export_button": "导出Excel",
        "reset_filters_button": "重置筛选",
        "close_description_button": "关闭",
        # Results section
        "recommended_jobs_table_title": "推荐职位",
        "no_description": "无描述",
        "url": "[原网址]({url})",
        "no_link": "无链接",
        # Job table headers
        "columnDefs": COLUMN_DEFS["zh"],
        # Modals
        "job_description_title": "工作内容详情",
        "full_description": "无详细内容",
        # Alerts and messages
        "resume_upload_notification": "简历已上传: {resume_filename}",
        "resume_parsed": "成功解析简历: {resume_filename}",
        "no_input_warning": "请至少输入求职意向或上传简历",
        "invalid_file_extension_warning": "简历仅支持以下文件格式: {ACCEPTED_RESUME_FILE_EXTENSION}",
        "parse_error": "简历解析失败: {resume_filename} ",
        "query_error": "求职意向分析失败",
        "match_error": "职位匹配失败",
        "toggle_job_description_hint": dcc.Markdown(
            "**双击 `工作内容` 以查看全部内容**"
        ),
        # Recruitment types
        "recruitment_type": {
            RecruitmentType.EXPERIENCED.name: "社招",
            RecruitmentType.GRADUATE.name: "校招",
            RecruitmentType.INTERN.name: "实习",
        },
        # Education levels
        "education": {
            AcademicQualification.ALL.name: "不限",
            AcademicQualification.ASSOCIATE.name: "大专",
            AcademicQualification.UNDERGRADUATE.name: "本科",
            AcademicQualification.MASTERS.name: "硕士",
            AcademicQualification.DOCTOR.name: "博士",
        },
    },
}
