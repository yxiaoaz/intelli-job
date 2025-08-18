# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import base64
import uuid
import os
from datetime import datetime
import concurrent.futures
from typing import Any, Dict, List

import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd

from app.core.user_analysis_agent import UserAnalysisAgent
from app.core.job_matching_agent import JobMatchingAgent
from app.models.job import JobItem
from app.models.constant import AcademicQualification, RecruitmentType
from app.static.frontend_utils import TRANSLATIONS, COLUMN_DEFS
from app.services.language_modeling.utils import ACCEPTED_RESUME_FILE_EXTENSION

user_agent = UserAnalysisAgent()
job_agent = JobMatchingAgent()

# Initialize the app with responsive meta tags
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.SUPERHERO,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css",
    ],
)
server = app.server
app.title = "IntelliJob - AI求职助手"

# Column definitions with responsive adjustments
# default use Chinese
columnDefs = COLUMN_DEFS['zh']

# Job description modal
description_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle(TRANSLATIONS['zh']["job_description_title"], id="job-description-title")),
        dbc.ModalBody(id="job-description-content"),
        dbc.ModalFooter(
            dbc.Button(id="close-description", className="ms-auto", n_clicks=0)
        ),
    ],
    id="description-modal",
    size="lg",
    scrollable=True,
    backdrop="static",
    className="modal-fullscreen-sm-down",  # Fullscreen on mobile
)

language_switch = dcc.Dropdown(
    id='language-selector',
    options=[
        {
            'label': html.Span('English', style={'color': 'black'}),
            'value': 'en'
        },
        {
            'label': html.Span('中文', style={'color': 'black'}),
            'value': 'zh'
        }
    ],
    value='zh',
    clearable=False,
    style={'width': '120px'}
)

# Main app layout with responsive design
app.layout = dbc.Container(
    [
        dcc.Download(id="download-data"),
        
   
        # user-input-status.data can take on values:
        #   "resume_parsed": when the resume is successfully parsed
        #   "invalid_file_extension_warning": when the resume file extension is not valid
        #   "no_input_warning": when both user input and resume files are empty
        #   "parser_error": the resume file cannot be parsed
        #   "query_error": something went wrong in analyzing the query
        #   "" : default
        dcc.Store(id="user-input-status"),
        # the raw underlying data as they are stored in SQL database
        # the displayed data will vary based on the language selected
        dcc.Store(id='raw-job-results-grid-data'), 
        # Responsive navbar
        dbc.NavbarSimple(
            brand=html.Span(
                [
                    html.Span("Intelli Job", className="d-inline d-md-none"),
                    html.Span("Intelli Job: 智能求职助手", className="d-none d-md-inline"),
                ]
            ),
            brand_href="#",
            color="primary",
            dark=True,
            className="mb-2 py-2",
            fluid=True,
            children=[
                language_switch, 
                dbc.NavItem(
                    dbc.NavLink(
                        [
                            html.Span("By: ", className="me-1 d-none d-sm-inline"),
                            html.Strong("yicong.xiao", className="me-2"),
                            html.I(className="bi bi-github me-1 d-none d-sm-inline"),
                            html.A(
                                "GitHub",
                                href="https://github.com/yxiaoaz",
                                target="_blank",
                                className="me-3 text-light text-decoration-none d-none d-sm-inline",
                            ),
                            html.I(className="bi bi-linkedin me-1 d-none d-sm-inline"),
                            html.A(
                                "LinkedIn",
                                href="https://linkedin.com/in/edwardxiao2001",
                                target="_blank",
                                className="text-light text-decoration-none d-none d-sm-inline",
                            ),
                            html.I(className="bi bi-github d-inline d-sm-none me-2"),
                            html.I(className="bi bi-linkedin d-inline d-sm-none"),
                        ],
                        href="#",
                        className="text-light",
                    )
                )
            ],
        ),
        dbc.Row(
            [
                # Left column - input forms
                dbc.Col(
                    [
                        # Job search target card
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    html.H4(TRANSLATIONS['zh']['job_search_target_title'],id="job-search-target-title", className="card-title mb-0")  # ”求职意向“
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Textarea(
                                            id="user-query",
                                            placeholder=TRANSLATIONS['zh']['job_search_target_placeholder'],
                                            style={
                                                "width": "100%",
                                                "height": 120,
                                                "fontSize": "14px",
                                            },
                                        ),
                                    ],
                                    className="py-2",
                                ),
                            ],
                            className="mb-3",
                        ),
                        # Resume upload card
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H4(
                                            TRANSLATIONS['zh']['upload_resume_title'],
                                            id = "upload-resume-title",
                                            className="card-title mb-2",
                                        ),
                                        dcc.Upload(
                                            TRANSLATIONS['zh']['upload_resume_text'],
                                            id="upload-resume",
                                            style={
                                                "width": "100%",
                                                "height": "60px",
                                                "lineHeight": "60px",
                                                "borderWidth": "1px",
                                                "borderStyle": "dashed",
                                                "borderRadius": "5px",
                                                "textAlign": "center",
                                                "fontSize": "14px",
                                            },
                                            multiple=False,
                                        ),
                                        dbc.Button(
                                            TRANSLATIONS['zh']['remove_resume_text'],
                                            id="remove-resume",
                                            color="danger",
                                            outline=True,
                                            className="mt-2 w-100",
                                            size="sm",
                                        ),
                                        html.Div(
                                            id="resume-upload-notification", className="mt-2"
                                        ),
                                        html.Div(
                                            id="user-input-status-display",
                                            className="mt-2",
                                        ),
                                    ],
                                    className="py-2",
                                )
                            ],
                            className="mb-3",
                        ),
                        # Search options card
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H5(id="search-options-title", className="mb-0")),
                                dbc.CardBody(
                                    [
                                        html.Div(
                                            [
                                                dbc.RadioItems(
                                                    id="search-mode",
                                                    options=[
                                                        {
                                                            "label": "语义搜索",
                                                            "value": "semantic",
                                                        },
                                                        {
                                                            "label": "关键词搜索",
                                                            "value": "sparse",
                                                        },
                                                        {
                                                            "label": "混合搜索",
                                                            "value": "hybrid",
                                                        },
                                                    ],
                                                    value="hybrid",
                                                    inline=False,  # Stack vertically on mobile
                                                    class_name="mt-2",
                                                ),
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-info-circle"
                                                    ),
                                                    id="search-mode-info",
                                                    color="link",
                                                    className="ms-2 p-0",
                                                    style={"fontSize": "1rem"},
                                                ),
                                                dbc.Tooltip(
                                                    TRANSLATIONS['zh']['search_mode_tooltip'],
                                                    id = "search-mode-tooltip",
                                                    target="search-mode-info",
                                                    placement="right",
                                                ),
                                            ],
                                            className="d-flex align-items-center mb-2",
                                        ),
                                        html.Div(
                                            [
                                                dbc.Label(
                                                    TRANSLATIONS['zh']['topk_label'],
                                                    id = "topk-label", # "返回职位数:"
                                                    html_for="topk-input",
                                                    className="me-2",
                                                ),
                                                dbc.Input(
                                                    id="topk-input",
                                                    type="number",
                                                    min=1,
                                                    max=5000,
                                                    step=1,
                                                    value=500, 
                                                    style={
                                                        "width": "80px",
                                                        "display": "inline-block",
                                                    },
                                                    size="sm",
                                                ),
                                                dbc.Button(
                                                    html.I(
                                                        className="bi bi-info-circle"
                                                    ),
                                                    id="topk-info", 
                                                    color="link",
                                                    className="ms-2 p-0",
                                                    style={"fontSize": "1rem"},
                                                ),
                                                dbc.Tooltip(
                                                    TRANSLATIONS['zh']['topk_tooltip'],
                                                    id = "topk-tooltip", # "设置返回的职位数量（1-5000)""
                                                    target="topk-info",
                                                    placement="right",
                                                ),
                                            ],
                                            className="d-flex align-items-center",
                                        ),
                                    ],
                                    className="py-2",
                                ),
                            ],
                            className="mb-3",
                        ),
                        dbc.Button(
                            TRANSLATIONS['zh']['match_button'],
                            id="match-button",
                            color="primary",
                            className="w-100 mb-3",
                            size="lg",
                        ),
                    ],
                    width=12,
                    lg=4,
                    className="mb-4",
                ),
                # Right column - results table
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader( 
                                    html.H4(id = "recommended-jobs-table-title", className="m-0") # e.g. "推荐职位"
                                ),
                                dbc.CardBody(
                                    [
                                        html.Div(
                                            dbc.Spinner(color="primary"),
                                            id="loading-resume",
                                            style={"display": "none"},
                                            className="text-center my-3",
                                        ),
                                        html.Div(
                                            dag.AgGrid(
                                                id="job-results-grid",
                                                columnDefs=columnDefs,
                                                dashGridOptions={
                                                    "pagination": True,
                                                    "paginationPageSize": 5,
                                                    "tooltipShowDelay": 500,
                                                    "rowHeight": 60,
                                                    "suppressHorizontalScroll": False,
                                                    "domLayout": "autoHeight",
                                                    "headerHeight": 60,
                                                },
                                                style={
                                                    "width": "100%",
                                                    "height": "100%",
                                                    "minHeight": "300px"
                                                },
                                                className="ag-theme-alpine-dark",
                                            ),
                                            style={
                                                "flex": "1",
                                                "minHeight": "0",  
                                                "display": "flex",
                                                "flexDirection": "column"
                                            }
                                        ),
                                        description_modal,
                                        dbc.Label(
                                                    TRANSLATIONS['zh']['toggle_job_description_hint'],
                                                    id = "toggle-job-description-hint", 
                                                    className="me-2",
                                                ),
                                        dbc.ButtonGroup(
                                            [
                                                dbc.Button(
                                                    TRANSLATIONS['zh']['export_button'],
                                                    id="export-button",
                                                    color="success",
                                                    className="mb-2 w-100",
                                                ),
                                                dbc.Button(
                                                    TRANSLATIONS['zh']['reset_filters_button'],
                                                    id="reset-filters",
                                                    outline=True,
                                                    className="w-100",
                                                )
                                            ],
                                            className="mt-3",
                                            vertical=True,
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "height": "100%",
                                        "padding": "0.75rem" 
                                    },
                                ),
                            ],
                            style={
                                "height": "100%",
                                "display": "flex",
                                "flexDirection": "column"
                            },
                        )
                    ],
                    width=12,
                    lg=8,
                    className="mb-4",
                    style={"height": "100%"}
                )
            ],
            className="g-3",
        ),
    ],
    fluid=True,
    className="px-2 px-md-3 py-2",
    style={"maxWidth": "1200px"},
)

################ MAIN CALLBACK ################
def analyze_resume_file(resume_content, resume_filename, language):
    content_type, content_string = resume_content.split(",")
    decoded = base64.b64decode(content_string)
    temp_path = f"temp_resume_{uuid.uuid4().hex}_{resume_filename}"
    with open(temp_path, "wb") as f:
        f.write(decoded)
    try:
        user_resume_profile = user_agent.analyze_resume(temp_path)
    finally:
        os.remove(temp_path)
    resume_output = "resume_parsed"
    return user_resume_profile, resume_output


def analyze_query_text(query_text):
    user_query_preference = user_agent.analyze_query(query_text)
    return user_query_preference

def format_single_row_raw_data(single_row_raw_data: Dict[str, Any], language):
    res = single_row_raw_data.copy()

    res["recruitment_type"] = TRANSLATIONS[language]["recruitment_type"][single_row_raw_data["recruitment_type"]]
    res["education"] = TRANSLATIONS[language]["education"][single_row_raw_data["education"]]
    res["url"] = TRANSLATIONS[language]["url"].format(url=single_row_raw_data["url"])
    
    return res

def format_multiple_row_raw_data(multiple_row_raw_data: List[Dict[str, Any]], language):
    res =[]
    
    if not multiple_row_raw_data:
        return res
    
    for single_row_raw_data in multiple_row_raw_data:
        res.append(format_single_row_raw_data(single_row_raw_data, language))
    
    return res

@app.callback(
    [   
        Output("raw-job-results-grid-data", "data"),
        Output("job-results-grid", "rowData", allow_duplicate=True),
        Output("user-input-status", "data", allow_duplicate=True),
        Output("loading-resume", "children")
    ],
        Input("match-button", "n_clicks"),
    [
        State("user-query", "value"),
        State("upload-resume", "contents"),
        State("upload-resume", "filename"),
        State("search-mode", "value"),
        State("topk-input", "value"),
        State('language-selector', 'value') 
    ],
    prevent_initial_call=True,
    running=[
        (Output("match-button", "disabled"), True, False),
        (Output("loading-resume", "style"), {"display": "block"}, {"display": "none"})
    ],
)
def analyze_and_match(
    n_clicks, query_text, resume_content, resume_filename, search_mode, top_k, language
):
    if not query_text and not resume_content:
        return [], [], TRANSLATIONS[language]["no_input_warning"], dash.no_update

    if (
        resume_content
        and os.path.splitext(resume_filename)[-1] not in ACCEPTED_RESUME_FILE_EXTENSION
    ):
        return (
            [],
            [],
            TRANSLATIONS[language]["invalid_file_extension_warning"],
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
                analyze_resume_file, resume_content, resume_filename, language
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
                        [],
                        TRANSLATIONS[language]['parse_error'],
                        dash.no_update,
                    )
                elif key == "query":
                    return (
                        [],
                        [],
                        TRANSLATIONS[language]['query_error'],
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
        raw_data = []
        job_description_cutoff_length = 20
        for item in results:
            job = item["job_item"]
            raw_data.append(
                {
                    "id": str(job.id),
                    "company": job.company_name,
                    "title": job.job_title,
                    "recruitment_type": job.recruitment_type.name,
                    "location": job.location,
                    "salary": job.salary,
                    "education": job.min_academic_qualification.name,
                    "update_time": job.update_time.strftime("%Y-%m-%d"),
                    "description": (
                        job.description[:job_description_cutoff_length] + "..."
                    )
                    if job.description
                    and len(job.description) > job_description_cutoff_length
                    else (job.description or "NA"),
                    "full_description": job.description,
                    "url": job.url,
                }
            )
        
        formatted_results = format_multiple_row_raw_data(raw_data, language)

        if resume_output is not None:
            return raw_data, formatted_results, resume_output, dash.no_update
        else:
            return raw_data, formatted_results, "", dash.no_update
    except Exception as e:
        return [], [], TRANSLATIONS[language]['match_error'], dash.no_update


################################
@app.callback(
    [
    #Output('navbar-brand-text', 'children'),
     #Output('navbar-brand-full-text', 'children'),
     Output('job-search-target-title', 'children'),
     Output('user-query', 'placeholder'),
     Output('upload-resume-title', 'children'),
     Output('upload-resume', 'children'),
     Output('remove-resume', 'children'),
     Output('search-options-title', 'children'),
     Output('search-mode', 'options'),
     Output('search-mode-tooltip', 'children'),
     Output('topk-label', 'children'),
     Output('topk-tooltip', 'children'),
     Output('match-button', 'children'),
     Output('export-button', 'children'),
     Output('reset-filters', 'children'),
     Output('close-description', 'children'),
     Output('recommended-jobs-table-title', 'children'),
     Output('job-results-grid', 'columnDefs'),
     Output('job-results-grid', 'rowData', allow_duplicate=True),
     Output("job-description-title", "children"),
     Output('toggle-job-description-hint', 'children')
     ],
    Input('language-selector', 'value'),
    [   
        State("raw-job-results-grid-data", "data")
    ],
    prevent_initial_call=True,
)
def on_switch_language(selected_lang, raw_row_data):
    """
    Change language for the following stuffs:

        - Navigation bar:
            - Product name: "navbar-brand-text"
        - Job search target card:
            - The card title : "job-search-title"
            - The placeholder input : "user-query".placeholder
        - Resume upload card:
            - The card title: "upload-resume-title"
            - The text in the upload area: "upload-resume", use display_dict["upload_resume_text"] 
            - The text on the remove resume button: "remove-resume"n, use display_dict["remove_resume_text"]
        - Search options card: 
            - The card title: "search-options-title"
            - The search options: "search-mode".options, use display_dict["search_mode_options"]
            - The search option tool tip: "search-mode-tooltip"
            - The top-k option input box: "topk-info"
            - The top-k option tool tip: "topk-tooltip"
        - Buttons: 
            - match-button
            - export-button
            - reset-filters
            - close-description
        - Result section:
            - "recommended-jobs-table-title"
            - Job table column names
        - Full job description panel(modal):
            - "job-description-title"
            - "toggle-job-description-hint"

    """
    display_dict = TRANSLATIONS[selected_lang]

    return (
        #display_dict['navbar_brand'],
        #display_dict['app_title'],
        display_dict['job_search_target_title'],
        display_dict['job_search_target_placeholder'],
        display_dict['upload_resume_title'],
        display_dict['upload_resume_text'],
        display_dict['remove_resume_text'],
        display_dict['search_options_title'],
        display_dict['search_mode_options'],
        display_dict['search_mode_tooltip'],
        display_dict['topk_label'],
        display_dict['topk_tooltip'],
        display_dict['match_button'],
        display_dict['export_button'],
        display_dict['reset_filters_button'],
        display_dict['close_description_button'],
        display_dict['recommended_jobs_table_title'],
        display_dict['columnDefs'],
        format_multiple_row_raw_data(raw_row_data, selected_lang),
        display_dict['job_description_title'],
        display_dict['toggle_job_description_hint'],
    )

# download excel
@app.callback(
    Output("download-data", "data"),
    Input("export-button", "n_clicks"),
    State("job-results-grid", "rowData"),
    prevent_initial_call=True,
)
def on_export_button_click(n_clicks, rows):
    """
    Downlad the recommended jobs as csv file
    """
    if not rows:
        raise dash.exceptions.PreventUpdate

    try:
        df = pd.DataFrame(rows)

        # drop the short description snippet, retain the full description of the job
        df = df.drop(columns=["id", "description"], errors="ignore")
        return dcc.send_data_frame(df.to_csv, "job_recommendations.csv", encoding="utf-8-sig", index=False)
    except Exception as e:
        raise dash.exceptions.PreventUpdate


@app.callback(
    [
        Output("resume-upload-notification", "children", allow_duplicate=True),
        Output("user-input-status", "data", allow_duplicate=True),
    ],
        Input("upload-resume", "contents"),
    [   
        State("upload-resume", "filename"),
        State('language-selector', 'value')
    ],
    prevent_initial_call=True,
)
def on_resume_upload_button_click(contents, filename, language):
    """
    Handle the ui change after resume upload button is clicked.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return "", ""
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # after uploading resume, should immediately notify user
    if trigger_id == "upload-resume" and contents:
        return (dbc.Alert(
                TRANSLATIONS[language]['resume_upload_notification'].format(resume_filename = filename),
                color="info",
                className="d-flex align-items-center",
            ),
            "",
        )

    return "", ""


@app.callback(
    [
        Output("resume-upload-notification", "children", allow_duplicate=True),  # "简历已上传"
        Output("user-input-status", "data", allow_duplicate=True),  # "成功解析简历"
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
    2. Remove all resume data, in dcc.Store(id='user-input-status') and State('upload-resume', 'contents')
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return (dash.no_update,) * 4

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "remove-resume":
        return "", "", "", ""

    return "", "", "", ""


@app.callback(
   [
       Output("user-input-status-display", "children"),
       Output("resume-upload-notification", "children", allow_duplicate=True)
    ],
    [
        Input("user-input-status", "data"),
        Input("resume-upload-notification", "children"),
        Input('language-selector', 'value')
    ],
    State("upload-resume", "filename"),
    prevent_initial_call=True,
)
def display_alerts_and_notifications(user_input_status, resume_upload_notification, language, resume_filename):
    """
    This function renders the view of the underlying 'user-input-status.data' and 'resume_upload_notification'
    whenever there's a change to it (including underlying data and **language chane**)
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    user_input_status_display, new_resume_upload_notification = dash.no_update, dash.no_update

    # displays whatever change to resume parse result
    if trigger_id in ["user-input-status", "language-selector"]:
        if user_input_status == "resume_parsed":
            user_input_status_display = dbc.Alert(
                                html.Div(
                                    [html.I(className="bi bi-check-circle me-2"), TRANSLATIONS[language]['resume_parsed'].format(resume_filename = resume_filename)]
                                ),
                                color="success",
                                className="d-flex align-items-center",
                            )
        if user_input_status == "no_input_warning":
            user_input_status_display = dbc.Alert(TRANSLATIONS[language]['no_input_warning'], color="warning")
        if user_input_status == "parse_error":
            user_input_status_display = dbc.Alert(TRANSLATIONS[language]['parse_error'].format(resume_filename=resume_filename), color="danger")
        if user_input_status == "query_error":
            user_input_status_display = dbc.Alert(TRANSLATIONS[language]['query_error'], color="danger")
        if user_input_status == "match_error":
            user_input_status_display = dbc.Alert(TRANSLATIONS[language]['match_error'], color="danger")
        if user_input_status == "invalid_file_extension_warning":
            user_input_status_display = dbc.Alert(TRANSLATIONS[language]['invalid_file_extension_warning'].format(ACCEPTED_RESUME_FILE_EXTENSION = ACCEPTED_RESUME_FILE_EXTENSION), color="warning")

    # if switch language and there was a displayed notification for resume uploaded, need to translate it as well
    if trigger_id == "language-selector" and resume_upload_notification:
        new_resume_upload_notification = dbc.Alert(
                TRANSLATIONS[language]['resume_upload_notification'].format(resume_filename = resume_filename),
                color="info",
                className="d-flex align-items-center",
            )
    
    return user_input_status_display, new_resume_upload_notification


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
        description = rows[int(cell['rowId'])].get("full_description", "NO VALUE")
        return True, dcc.Markdown(description)

    return is_open, ""


if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "False") == "True"
    host = os.environ.get("HOST", "127.0.0.1")
    #app.run(host=host, port=int(os.environ.get("PORT", 5002)), debug=True)
    app.run(host=host, port=5002, debug=True)
