import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import base64
import json
import uuid
import os
from datetime import datetime



# 初始化后端服务
from app.core.user_analysis_agent import UserAnalysisAgent
from app.core.job_matching_agent import JobMatchingAgent
from app.models.job import JobItem

user_agent = UserAnalysisAgent()
job_agent = JobMatchingAgent()

# 创建Dash应用
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "IntelliJob AI求职助手"

# 布局设计
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("AI求职助手", className="text-center my-4"))),
    
    # 输入区
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
                dag.AgGrid(
                    id='job-results-grid',
                    columnDefs=[
                        {"headerName": "公司", "field": "company", "filter": True, "flex": 1},
                        {"headerName": "职位", "field": "title", "filter": True, "flex": 1},
                        {
                            "headerName": "匹配度", 
                            "field": "score", 
                            "type": "rightAligned",
                            "valueFormatter": {"function": "d3.format('.1%')(params.value)"},
                            "cellStyle": {"styleConditions": [
                                {"condition": "params.value >= 0.8", "style": {"color": 'green'}},
                                {"condition": "params.value >= 0.6", "style": {"color": 'orange'}},
                                {"condition": "params.value < 0.6", "style": {"color": 'red'}}
                            ]},
                            "width": 120
                        },
                        {"headerName": "地点", "field": "location", "width": 100},
                        {"headerName": "类型", "field": "job_type", "width": 100},
                        {
                            "headerName": "详情", 
                            "field": "url", 
                            "cellRenderer": "markdown",
                            "width": 120,
                            "autoHeight": True
                        }
                    ],
                    defaultColDef={
                        "sortable": True,
                        "resizable": True,
                        "filter": True,
                        "floatingFilter": True
                    },
                    dashGridOptions={
                        "pagination": True,
                        "paginationPageSize": 20,
                        "domLayout": "autoHeight",
                        "animateRows": True
                    },
                    style={'width': '100%', 'height': None}
                ),
                dbc.Button(
                    "导出结果", 
                    id="export-button", 
                    color="success", 
                    className="mt-3",
                    outline=True
                ),
                dcc.Download(id="download-data")
            ])
        ])
    ]))
], fluid=True)

# 回调处理
@app.callback(
    [Output('job-results-grid', 'rowData'),
     Output('resume-analysis-output', 'children')],
    [Input('match-button', 'n_clicks')],
    [State('user-query', 'value'),
     State('upload-resume', 'contents'),
     State('upload-resume', 'filename'),
     State('search-mode', 'value')],
    prevent_initial_call=True
)
def analyze_and_match(n_clicks, query_text, resume_content, resume_filename, search_mode):
    if not query_text and not resume_content:
        return [], dbc.Alert("请至少输入求职意向或上传简历", color="warning")
    
    user_query_preference = {}
    user_resume_profile = {}
    
    # 分析求职意向
    if query_text:
        try:
            print(f"Analyzing user query: {query_text}")
            user_query_preference = user_agent.analyze_query(query_text)
            print(f"Query analysis result: {user_query_preference}")
        except Exception as e:
            return [], dbc.Alert(f"求职意向分析失败: {str(e)}", color="danger")
    
    # 解析简历
    resume_output = None
    if resume_content:
        try:
            content_type, content_string = resume_content.split(',')
            decoded = base64.b64decode(content_string)
            temp_path = f"temp_resume_{uuid.uuid4().hex}.pdf"
            with open(temp_path, "wb") as f:
                f.write(decoded)
            
            user_resume_profile = user_agent.analyze_resume(temp_path)
            os.remove(temp_path)
            
            resume_output = dbc.Alert(f"成功解析简历: {resume_filename}", color="success")
        except Exception as e:
            return [], dbc.Alert(f"简历解析失败: {str(e)}", color="danger")

    # 执行职位匹配
    try:
        results = job_agent.match_jobs(
            user_query_preference=user_query_preference,
            user_resume_profile=user_resume_profile,
            search_mode=search_mode
        )
        
        # 格式化结果
        formatted_results = []
        for item in results:
            job: JobItem = item["job_item"]
            formatted_results.append({
                "id": str(job.id),
                "company": job.company_name,
                "title": job.job_title,
                "job_type": str(job.recruitment_type),
                "score": item["score"],
                "location": job.location,
                "update_time": job.update_time,
                "url": f"[职位详情]({job.url})"
            })
        
        return formatted_results, resume_output
    except Exception as e:
        return [], dbc.Alert(f"职位匹配失败: {str(e)}", color="danger")

# 导出功能
@app.callback(
    Output("download-data", "data"),
    Input("export-button", "n_clicks"),
    State("job-results-grid", "rowData"),
    prevent_initial_call=True
)
def export_results(n_clicks, rows):
    if not rows:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(rows)
    df['score'] = df['score'].apply(lambda x: f"{x:.1%}")
    return dcc.send_data_frame(df.to_excel, "职位推荐结果.xlsx", index=False)

if __name__ == '__main__':
    app.run(debug=True)