# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import base64
import uuid
import os
from datetime import datetime
import concurrent.futures

import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd


from app.core.user_analysis_agent import UserAnalysisAgent
from app.core.job_matching_agent import JobMatchingAgent
from app.models.job import JobItem
from app.models.constant import AcademicQualification, RecruitmentType
from app.services.language_modeling.utils import ACCEPTED_RESUME_FILE_EXTENSION

user_agent = UserAnalysisAgent()
job_agent = JobMatchingAgent()


app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.SUPERHERO,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css",
    ],
)
server = app.server
app.title = "IntelliJob - AI求职助手"


# for the result table
columnDefs = [
    {
        "headerName": "发布时间 (Time of Posting)",
        "field": "update_time",
        "width": 120,
        "filter": "agDateColumnFilter",
        "filterParams": {
            "browserDatePicker": True,
            "minValidYear": 2000,
            "maxValidYear": datetime.now().year + 1,
        },
    },
    {"headerName": "公司 (Company Name)", "field": "company", "filter": True, "flex": 1},
    {"headerName": "职位 (Job Title)", "field": "title", "filter": True, "flex": 1},
    # {
    #     "headerName": "匹配度",
    #     "field": "score",
    #     "type": "rightAligned",
    #     "valueFormatter": {"function": "d3.format('.1%')(params.value)"},
    #     "cellStyle": {"styleConditions": [
    #         {"condition": "params.value >= 0.8", "style": {"color": 'green'}},
    #         {"condition": "params.value >= 0.6", "style": {"color": 'orange'}},
    #         {"condition": "params.value < 0.6", "style": {"color": 'red'}}
    #     ]},
    #     "width": 120
    # },
    {"headerName": "地点 (Location)", "field": "location", "width": 100},
    {
        "headerName": "工作类型 (Recruitment Type)",
        "field": "recruitment_type",
        "width": 100,
        "filter": "agSetColumnFilter",
        "filterParams": {
            "values": [rc.value for rc in RecruitmentType],
            "suppressAndOrCondition": True,
        },
    },
    {
        "headerName": "薪资 (Salary)",
        "field": "salary",
        "width": 120,
        "filter": False,
        # "filter": "agSetColumnFilter",
        # "filterParams": {
        #     "filterOptions": ["contains", "notContains"],
        #     "suppressAndOrCondition": True
        # }
    },
    {
        "headerName": "最低学历要求 (Mininum Education Qualification)",
        "field": "education",
        "width": 100,
        "filter": "agSetColumnFilter",
        "filterParams": {
            "values": [ac.value for ac in AcademicQualification],
            "suppressAndOrCondition": True,
        },
    },
    {
        "headerName": "工作内容 (Duties and Requirements)",
        "field": "description",
        "tooltipField": "description",
        "cellRenderer": "html",
        "wrapText": True,
        "autoHeight": True,
        "filter": False,
        "resizable": True,
    },
    {
        "headerName": "源链接 (URL)",
        "field": "url",
        "cellRenderer": "markdown",
        "width": 120,
        "autoHeight": True,
    },
]

# the job description can be long
# the design is to show a snippet
# user can toggle or click to view whole content
description_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("工作内容详情 / Job Description Details")),
        dbc.ModalBody(id="job-description-content"),
        dbc.ModalFooter(
            dbc.Button("关闭", id="close-description", className="ms-auto", n_clicks=0)
        ),
    ],
    id="description-modal",
    size="lg",
    scrollable=True,
    backdrop="static",
)

# layout of the whole interface
app.layout = dbc.Container(
    [
        dcc.Download(id="download-data"),
        dcc.Store(id="resume-parse-result"),
        dbc.NavbarSimple(
            brand="Intelli Job: 智能求职助手",
            color="primary",
            dark=True,
            className="mb-4",
            children=[
                dbc.NavItem(
                    dbc.NavLink(
                        [
                            html.Span(
                                "By: ", className="me-1", style={"color": "#333"}
                            ),
                            html.Strong("yicong.xiao", className="me-2"),
                            html.I(className="bi bi-github me-1"),
                            html.A(
                                "GitHub",
                                href="https://github.com/yxiaoaz",
                                target="_blank",
                                className="me-3 text-light text-decoration-none",
                            ),
                            html.I(className="bi bi-linkedin me-1"),
                            html.A(
                                "LinkedIn",
                                href="https://linkedin.com/in/edwardxiao2001",
                                target="_blank",
                                className="text-light text-decoration-none",
                            ),
                        ],
                        href="#",
                        className="text-light",
                    )
                )
            ],
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        # 求职意向 card
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    html.H4(
                                        [
                                            "求职意向描述",
                                            html.Br(),
                                            "Describe your job search target",
                                        ],
                                        className="card-title",
                                    )
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Textarea(
                                            id="user-query",
                                            placeholder="例如：2024届计算机硕士，擅长Python和机器学习，想找北京的数据分析工作...\ne.g. I am looking for graduate jobs in data science",
                                            style={"width": "100%", "height": 120},
                                        ),
                                    ]
                                ),
                            ],
                            class_name="mb-4 flex-fill",
                        ),
                        # 上传简历 card
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H4(
                                            [
                                                "上传简历 (支持 .pdf/.docx/.doc 格式)",
                                                html.Br(),
                                                "Upload Resume (supporting .pdf/.docx/.doc format)",
                                            ],
                                            className="card-title",
                                        ),
                                        dcc.Upload(
                                            id="upload-resume",
                                            children=html.Div(["拖放或 ", html.A("选择文件")]),
                                            style={
                                                "width": "100%",
                                                "height": "60px",
                                                "lineHeight": "60px",
                                                "borderWidth": "1px",
                                                "borderStyle": "dashed",
                                                "borderRadius": "5px",
                                                "textAlign": "center",
                                            },
                                            multiple=False,
                                        ),
                                        dbc.Button(
                                            "移除简历 / Remove Resume",
                                            id="remove-resume",
                                            color="danger",
                                            outline=True,
                                            className="mt-2 w-100",
                                        ),
                                        html.Div(
                                            id="resume-upload-status", className="mt-2"
                                        ),
                                        html.Div(
                                            id="resume-analysis-output",
                                            className="mt-2",
                                        ),
                                    ]
                                )
                            ],
                            class_name="mb-4 flex-fill",
                        ),
                        # search options
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H5("检索设置 / Search Options")),
                                dbc.CardBody(
                                    [
                                        html.Div(
                                            [
                                                dbc.RadioItems(
                                                    id="search-mode",
                                                    options=[
                                                        {
                                                            "label": "语义搜索 (Semantic Search)",
                                                            "value": "semantic",
                                                        },
                                                        {
                                                            "label": "关键词搜索 (Keyword Search)",
                                                            "value": "sparse",
                                                        },
                                                        {
                                                            "label": "混合搜索 (Hybrid Search)",
                                                            "value": "hybrid",
                                                        },
                                                    ],
                                                    value="hybrid",
                                                    inline=True,
                                                    class_name="mt-2",
                                                ),
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-info-circle"
                                                    ),
                                                    id="search-mode-info",
                                                    color="link",
                                                    className="ms-2 p-0",
                                                    style={"fontSize": "1.2rem"},
                                                ),
                                                dbc.Tooltip(
                                                    "选择检索方式：语义搜索（智能匹配），关键词搜索（传统检索），混合搜索（结合两者）。\n"
                                                    "Select search mode: Semantic Search (matching by embedding similarity), Keyword Search (traditional), or Hybrid Search (combines both).",
                                                    target="search-mode-info",
                                                    placement="right",
                                                ),
                                            ],
                                            className="d-flex align-items-center mb-2",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    "返回Top-K职位数 / Number of results",
                                                    html_for="topk-input",
                                                    className="me-2",
                                                ),
                                                dbc.Input(
                                                    id="topk-input",
                                                    type="number",
                                                    min=1,
                                                    max=5000,
                                                    step=1,
                                                    value=800,
                                                    style={
                                                        "width": "100px",
                                                        "display": "inline-block",
                                                    },
                                                ),
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-info-circle"
                                                    ),
                                                    id="topk-info",
                                                    color="link",
                                                    className="ms-2 p-0",
                                                    style={"fontSize": "1.2rem"},
                                                ),
                                                dbc.Tooltip(
                                                    "设置每次检索返回的职位数量（1-5000）\n"
                                                    "Set the number of job results to return (1-5000)",
                                                    target="topk-info",
                                                    placement="right",
                                                ),
                                            ],
                                            className="d-flex align-items-center",
                                        ),
                                    ]
                                ),
                            ],
                            className="mt-3 w-100",
                        ),
                        dbc.Button(
                            "开始匹配 / Start Matching",
                            id="match-button",
                            color="primary",
                            className="mt-3 w-100",
                        ),
                    ],
                    width=4,
                    className="d-flex flex-column",
                    style={"height": "80vh"},
                ),
                # right column (results table)
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    html.H4("推荐职位 / Recommended Jobs", className="m-0")
                                ),
                                dbc.CardBody(
                                    [
                                        html.Div(
                                            dbc.Spinner(color="primary"),
                                            id="loading-resume",
                                            style={"display": "none"},
                                            className="text-center my-3",
                                        ),
                                        dag.AgGrid(
                                            id="job-results-grid",
                                            columnDefs=columnDefs,
                                            dashGridOptions={
                                                "pagination": True,
                                                "paginationPageSize": 10,
                                                "tooltipShowDelay": 500,
                                                "rowHeight": 80,
                                            },
                                            style={"height": "100%"},
                                        ),
                                        description_modal,
                                        dbc.ButtonGroup(
                                            [
                                                dbc.Button(
                                                    "导出Excel / Export to Excel",
                                                    id="export-button",
                                                    color="success",
                                                ),
                                                dbc.Button(
                                                    "重置筛选 / Reset Filters",
                                                    id="reset-filters",
                                                    outline=True,
                                                ),
                                            ],
                                            className="mt-3",
                                        ),
                                    ],
                                    style={"height": "100%"},
                                ),  # Fill card height
                            ],
                            className="h-100",
                        )
                    ],
                    width=8,
                    className="d-flex flex-column",
                    style={"height": "80vh"},
                ),
            ]
        ),
    ],
    fluid=True,
    style={"paddingBottom": "80px"},
)


################ MAIN CALLBACK ################
def analyze_resume_file(resume_content, resume_filename):
    content_type, content_string = resume_content.split(",")
    decoded = base64.b64decode(content_string)
    temp_path = f"temp_resume_{uuid.uuid4().hex}_{resume_filename}"
    with open(temp_path, "wb") as f:
        f.write(decoded)
    try:
        user_resume_profile = user_agent.analyze_resume(temp_path)
    finally:
        os.remove(temp_path)
    resume_output = dbc.Alert(
        html.Div(
            [html.I(className="bi bi-check-circle me-2"), f"成功解析简历: {resume_filename}"]
        ),
        color="success",
        className="d-flex align-items-center",
    )
    return user_resume_profile, resume_output


def analyze_query_text(query_text):
    user_query_preference = user_agent.analyze_query(query_text)
    return user_query_preference


@app.callback(
    [
        Output("job-results-grid", "rowData"),
        Output("resume-parse-result", "data", allow_duplicate=True),
        Output("loading-resume", "children"),
    ],
    Input("match-button", "n_clicks"),
    [
        State("user-query", "value"),
        State("upload-resume", "contents"),
        State("upload-resume", "filename"),
        State("search-mode", "value"),
        State("topk-input", "value"),
    ],
    prevent_initial_call=True,
    running=[
        (Output("match-button", "disabled"), True, False),
        (Output("loading-resume", "style"), {"display": "block"}, {"display": "none"}),
    ],
)
def analyze_and_match(
    n_clicks, query_text, resume_content, resume_filename, search_mode, top_k
):
    if not query_text and not resume_content:
        return [], dbc.Alert("请至少输入求职意向或上传简历", color="warning"), dash.no_update

    if (
        resume_content
        and os.path.splitext(resume_filename)[-1] not in ACCEPTED_RESUME_FILE_EXTENSION
    ):
        return (
            [],
            dbc.Alert(f"简历仅支持以下文件格式：{ACCEPTED_RESUME_FILE_EXTENSION}", color="warning"),
            dash.no_update,
        )

    user_query_preference = {}
    user_resume_profile = {}
    resume_output = None

    # parallel analysis of resume and query text
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {}
        if resume_content:
            futures["resume"] = executor.submit(
                analyze_resume_file, resume_content, resume_filename
            )
        if query_text:
            futures["query"] = executor.submit(analyze_query_text, query_text)

        for key, future in futures.items():
            try:
                result = future.result()
                if key == "resume":
                    user_resume_profile, resume_output = result
                elif key == "query":
                    user_query_preference = result
            except Exception as e:
                if key == "resume":
                    return (
                        [],
                        dbc.Alert(f"简历解析失败: {str(e)}", color="danger"),
                        dash.no_update,
                    )
                elif key == "query":
                    return (
                        [],
                        dbc.Alert(f"求职意向分析失败: {str(e)}", color="danger"),
                        dash.no_update,
                    )

    # job match (unchanged)
    try:
        results = job_agent.match_jobs(
            user_query_preference=user_query_preference,
            user_resume_profile=user_resume_profile,
            search_mode=search_mode,
            top_k=top_k,
        )
        formatted_results = []
        job_description_cutoff_length = 20
        for item in results:
            job = item["job_item"]
            formatted_results.append(
                {
                    "id": str(job.id),
                    "company": job.company_name,
                    "title": job.job_title,
                    "recruitment_type": job.recruitment_type.value,
                    "location": job.location,
                    "salary": job.salary,
                    "education": job.min_academic_qualification.value,
                    "update_time": job.update_time.strftime("%Y-%m-%d"),
                    "description": (
                        job.description[:job_description_cutoff_length] + "..."
                    )
                    if job.description
                    and len(job.description) > job_description_cutoff_length
                    else (job.description or "无描述"),
                    "full_description": job.description or "无详细内容",
                    "url": f"[详情]({job.url})" if job.url else "无链接",
                }
            )
        if resume_output is not None:
            return formatted_results, resume_output, dash.no_update
        else:
            return formatted_results, "", dash.no_update
    except Exception as e:
        return [], dbc.Alert(f"职位匹配失败: {str(e)}", color="danger"), dash.no_update


################################

# download excel
@app.callback(
    Output("download-data", "data"),
    Input("export-button", "n_clicks"),
    State("job-results-grid", "rowData"),
    prevent_initial_call=True,
)
def export_results(n_clicks, rows):
    if not rows:
        raise dash.exceptions.PreventUpdate

    try:
        df = pd.DataFrame(rows)

        # drop the short description snippet, retain the full description of the job
        df = df.drop(columns=["id", "description"], errors="ignore")
        return dcc.send_data_frame(df.to_csv, "job_recommendations.csv", index=False)
    except Exception as e:
        raise dash.exceptions.PreventUpdate


@app.callback(
    [
        Output("resume-upload-status", "children", allow_duplicate=True),
        Output("resume-parse-result", "data", allow_duplicate=True),
    ],
    Input("upload-resume", "contents"),
    State("upload-resume", "filename"),
    prevent_initial_call=True,
)
def on_resume_upload_button_click(contents, filename):
    """
    Handle the ui change after resume upload button is clicked.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return "", ""
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # after uploading resume, should immediately notify user
    if trigger_id == "upload-resume" and contents:
        return (
            dbc.Alert(
                f"简历已上传: {filename}",
                color="info",
                className="d-flex align-items-center",
            ),
            "",
        )

    return "", ""


@app.callback(
    [
        Output("resume-upload-status", "children", allow_duplicate=True),  # "简历已上传"
        Output("resume-parse-result", "data", allow_duplicate=True),  # "成功解析简历"
        Output("upload-resume", "contents"),
        Output("upload-resume", "filename"),
    ],
    Input("remove-resume", "n_clicks"),
    prevent_initial_call=True,
)
def on_resume_remove_button_click(
    remove_resume_click,
):
    """
    Handle the ui change after the remove resume button is clicked.

    1. Remove all previous alerts about resume upload status or parsing status
    2. Remove all resume data, in dcc.Store(id='resume-parse-result') and State('upload-resume', 'contents')
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return (dash.no_update,) * 4

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "remove-resume":
        return "", "", "", ""

    return "", "", "", ""


@app.callback(
    Output("resume-analysis-output", "children"),
    Input("resume-parse-result", "data"),
    prevent_initial_call=True,
)
def show_resume_analysis_output(parse_result):
    """
    The UI that shows the status of resume analysis process.
    This is a view of the underlying 'resume-parse-result.data'.
    This function is only executed on change of underlying data.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # displays whatever change to resume parse result
    if trigger_id == "resume-parse-result":
        return parse_result

    return ""


# reset all filters
@app.callback(
    Output("job-results-grid", "filterModel"),
    Input("reset-filters", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(n_clicks):
    return None


# show the full description
@app.callback(
    [
        Output("description-modal", "is_open"),
        Output("job-description-content", "children"),
    ],
    [Input("job-results-grid", "cellClicked"), Input("close-description", "n_clicks")],
    [State("description-modal", "is_open"), State("job-results-grid", "rowData")],
    prevent_initial_call=True,
)
def toggle_description(cell, close_click, is_open, rows):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, ""

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "close-description":
        return False, ""

    if cell and cell["colId"] == "description":
        description = next(
            (
                row.get("full_description", "无详细内容")
                for row in rows
                if row.get("description") == cell["value"]
            ),
            "无详细内容",
        )
        return True, dcc.Markdown(description)

    return is_open, ""


if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "False") == "True"
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=int(os.environ.get("PORT", 5002)), debug=True)
