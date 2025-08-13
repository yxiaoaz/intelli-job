import base64
import uuid
import os
from datetime import datetime

import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd

# 初始化后端服务
from app.core.user_analysis_agent import UserAnalysisAgent
from app.core.job_matching_agent import JobMatchingAgent
from app.models.job import JobItem
from app.models.constant import AcademicQualification, RecruitmentType


# 初始化服务
user_agent = UserAnalysisAgent()
job_agent = JobMatchingAgent()


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.title = "IntelliJob - AI求职助手"

recruitment_type_values = [rc.value for rc in RecruitmentType]

# 列定义
columnDefs = [
    {
        "headerName": "发布时间 (Time of Posting)",
        "field": "update_time",
        "width": 120,
        "filter": "agDateColumnFilter",
        "filterParams": {
            "browserDatePicker": True,
            "minValidYear": 2000,
            "maxValidYear": datetime.now().year + 1
        }
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
        "filterParams": {"values": recruitment_type_values, "suppressAndOrCondition": True,},
    },
    {
        "headerName": "薪资 (Salary)",
        "field": "salary",
        "width": 120,
        "filter": False,
        #"filter": "agSetColumnFilter",
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
        "filterParams": {"values": [ac.value for ac in AcademicQualification], "suppressAndOrCondition": True,},
    },
    {
        "headerName": "工作内容 (Duties and Requirements)",
        "field": "description",
        "tooltipField": "description",
        "cellRenderer": "html",
        "wrapText": True,
        "autoHeight": True,
        "filter": False,
        "resizable": True
    },
    {
        "headerName": "源链接 (URL)", 
        "field": "url", 
        "cellRenderer": "markdown",
        "width": 120,
        "autoHeight": True
    },
]

# 工作内容详情弹窗组件
description_modal = dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("工作内容详情")),
        dbc.ModalBody(id="job-description-content"),
        dbc.ModalFooter(
            dbc.Button(
                "关闭",
                id="close-description",
                className="ms-auto",
                n_clicks=0
            )
        )
    ],
    id="description-modal",
    size="lg",
    scrollable=True,
    backdrop="static"
)

# 应用布局
app.layout = dbc.Container([
    dcc.Download(id="download-data"),  # 文件下载组件
    
    dbc.Row(dbc.Col(html.H1("AI求职助手", className="text-center my-4"))),
    
    # 用户输入区
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("求职意向", className="card-title"),
                    dcc.Textarea(
                        id='user-query',
                        placeholder='例如：2024届计算机硕士，擅长Python和机器学习，想找北京的数据分析工作...',
                        style={'width': '100%', 'height': 120}
                    ),
                    dbc.RadioItems(
                        id='search-mode',
                        options=[
                            {'label': '语义搜索', 'value': 'semantic'},
                            {'label': '关键词搜索', 'value': 'sparse'},
                            {'label': '混合搜索', 'value': 'hybrid'}
                        ],
                        value='hybrid',
                        inline=True,
                        className="mt-2"
                    ),
                    dbc.Button("开始匹配", id='match-button', color="primary", className="mt-3")
                ])
            ])
        ], md=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("上传简历(PDF)", className="card-title"),
                    dcc.Upload(
                        id='upload-resume',
                        children=html.Div(['拖放或 ', html.A('选择文件')]),
                        style={
                            'width': '100%',
                            'height': '60px',
                            'lineHeight': '60px',
                            'borderWidth': '1px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center'
                        },
                        multiple=False
                    ),
                    html.Div(id='resume-analysis-output', className="mt-2")
                ])
            ])
        ], md=6)
    ], className="mb-4"),
    
    # 结果展示区
    dbc.Row(dbc.Col([
        dbc.Card([
            dbc.CardHeader(html.H4("推荐职位", className="m-0")),
            dbc.CardBody([
                html.Div(
                    dbc.Spinner(color="primary"),
                    id="loading-resume",
                    style={'display': 'none'},
                    className="text-center my-3"
                ),
                
                dag.AgGrid(
                    id='job-results-grid',
                    columnDefs=columnDefs,
                    dashGridOptions={
                        "pagination": True,
                        "paginationPageSize": 10,
                        "tooltipShowDelay": 500,
                        "rowHeight": 80
                    },
                    style={'height': '70vh'}
                ),
                
                description_modal,
                
                dbc.ButtonGroup([
                    dbc.Button("导出Excel", id="export-button", color="success"),
                    dbc.Button("重置筛选", id="reset-filters", outline=True)
                ], className="mt-3"),
            ])
        ])
    ]))
], fluid=True)

# 主回调：分析简历和匹配职位
@app.callback(
    [Output('job-results-grid', 'rowData'),
     Output('resume-analysis-output', 'children'),
     Output('loading-resume', 'children')],
    [Input('match-button', 'n_clicks')],
    [State('user-query', 'value'),
     State('upload-resume', 'contents'),
     State('upload-resume', 'filename'),
     State('search-mode', 'value'),],
    prevent_initial_call=True,
    running=[
        (Output('match-button', 'disabled'), True, False),
        (Output('loading-resume', 'style'), {'display': 'block'}, {'display': 'none'})
    ],
)
def analyze_and_match(n_clicks, query_text, resume_content, resume_filename, search_mode):
    if not query_text and not resume_content:
        return [], dbc.Alert("请至少输入求职意向或上传简历", color="warning"), dash.no_update
    
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    user_query_preference = {}
    user_resume_profile = {}
    resume_output = None
    
    # 简历解析
    if resume_content and triggered_id == 'match-button':
        try:
            content_type, content_string = resume_content.split(',')
            decoded = base64.b64decode(content_string)
            temp_path = f"temp_resume_{uuid.uuid4().hex}.pdf"
            
            with open(temp_path, "wb") as f:
                f.write(decoded)
            
            user_resume_profile = user_agent.analyze_resume(temp_path)
            os.remove(temp_path)
            
            resume_output = dbc.Alert(
                html.Div([
                    html.I(className="bi bi-check-circle me-2"),
                    f"成功解析简历: {resume_filename}"
                ]),
                color="success",
                className="d-flex align-items-center"
            )
        except Exception as e:
            return [], dbc.Alert(f"简历解析失败: {str(e)}", color="danger"), dash.no_update
    
    # 求职意向分析
    if query_text:
        try:
            user_query_preference = user_agent.analyze_query(query_text)
        except Exception as e:
            return [], dbc.Alert(f"求职意向分析失败: {str(e)}", color="danger"), dash.no_update
    
    # 职位匹配
    try:
        results = job_agent.match_jobs(
            user_query_preference=user_query_preference,
            user_resume_profile=user_resume_profile,
            search_mode=search_mode
        )

        print(type(results))
        print(results[0])
        
        formatted_results = []
        for item in results:
            job = item["job_item"]
            formatted_results.append({
                "id": str(job.id),
                "company": job.company_name,
                "title": job.job_title,
                "recruitment_type": job.recruitment_type.value,
                "location": job.location,
                #"score": item['score'],
                "salary": job.salary,
                "education": job.min_academic_qualification.value,
                "update_time": job.update_time.strftime("%Y-%m-%d"),
                "description": (job.description[:100] + "...") if job.description and len(job.description) > 100 else (job.description or "无描述"),
                "full_description": job.description or "无详细内容",
                "url": f"[详情]({job.url})" if job.url else "无链接"
            })
        
        return formatted_results, resume_output, dash.no_update
    except Exception as e:
        return [], dbc.Alert(f"职位匹配失败: {str(e)}", color="danger"), dash.no_update

# 导出Excel回调
@app.callback(
    Output("download-data", "data"),
    Input("export-button", "n_clicks"),
    State("job-results-grid", "rowData"),
    prevent_initial_call=True
)
def export_results(n_clicks, rows):
    if not rows:
        raise dash.exceptions.PreventUpdate
    
    try:
        df = pd.DataFrame(rows)
        # 移除内部使用的字段
        df = df.drop(columns=['id', 'full_description'], errors='ignore')
        return dcc.send_data_frame(df.to_excel, "职位推荐结果.xlsx", index=False)
    except Exception as e:
        raise dash.exceptions.PreventUpdate

# 重置筛选回调
@app.callback(
    Output("job-results-grid", "filterModel"),
    Input("reset-filters", "n_clicks"),
    prevent_initial_call=True
)
def reset_filters(n_clicks):
    return None

# 工作详情弹窗回调
@app.callback(
    [Output("description-modal", "is_open"),
     Output("job-description-content", "children")],
    [Input("job-results-grid", "cellClicked"),
     Input("close-description", "n_clicks")],
    [State("description-modal", "is_open"),
     State("job-results-grid", "rowData")],
    prevent_initial_call=True
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
            (row.get("full_description", "无详细内容") for row in rows if row.get("description") == cell['value']),
            "无详细内容"
        )
        return True, dcc.Markdown(description)
    
    return is_open, ""

if __name__ == '__main__':
    app.run(debug=True)