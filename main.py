import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import base64
import io
import json
from datetime import datetime

# 初始化后端Agent
from app.core.user_analysis_agent import UserAnalysisAgent
from app.core.job_matching_agent import JobMatchingAgent

user_agent = UserAnalysisAgent()
job_agent = JobMatchingAgent()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.title = "IntelliJob - AI求职助手"

# 布局设计
app.layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H1("AI求职助手", className="text-center my-4"))),
        # 输入区
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H4("求职意向分析", className="card-title"),
                                        dcc.Textarea(
                                            id="user-input",
                                            placeholder="例如：2024届计算机硕士，擅长Python和机器学习，想找北京的数据分析工作...",
                                            style={"width": "100%", "height": 100},
                                        ),
                                        html.Div(
                                            id="input-analysis-result", className="mt-2"
                                        ),
                                    ]
                                )
                            ]
                        )
                    ],
                    md=6,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H4(
                                            "上传简历(PDF)", className="card-title"
                                        ),
                                        dcc.Upload(
                                            id="upload-resume",
                                            children=html.Div(
                                                ["拖放或 ", html.A("选择文件")]
                                            ),
                                            style=upload_style,
                                            multiple=False,
                                        ),
                                        html.Div(id="resume-analysis-result"),
                                    ]
                                )
                            ]
                        )
                    ],
                    md=6,
                ),
            ],
            className="mb-4",
        ),
        # 结果展示区
        dbc.Row(
            dbc.Col(
                [
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H4("推荐职位", className="m-0")),
                            dbc.CardBody(
                                [
                                    dag.AgGrid(
                                        id="job-results-grid",
                                        columnDefs=[
                                            {
                                                "headerName": "公司",
                                                "field": "company",
                                                "filter": True,
                                            },
                                            {
                                                "headerName": "职位",
                                                "field": "title",
                                                "filter": True,
                                            },
                                            {
                                                "headerName": "匹配度",
                                                "field": "score",
                                                "type": "rightAligned",
                                                "valueFormatter": {
                                                    "function": "d3.format('.0%')(params.value)"
                                                },
                                            },
                                            {"headerName": "地点", "field": "location"},
                                            {"headerName": "类型", "field": "job_type"},
                                            {
                                                "headerName": "详情",
                                                "field": "url",
                                                "cellRenderer": "markdown",
                                            },
                                        ],
                                        defaultColDef={
                                            "sortable": True,
                                            "resizable": True,
                                            "filter": True,
                                            "floatingFilter": True,
                                            "minWidth": 150,
                                        },
                                        dashGridOptions={
                                            "pagination": True,
                                            "paginationPageSize": 20,
                                            "domLayout": "autoHeight",
                                        },
                                        style={"height": "600px"},
                                    ),
                                    dbc.Button(
                                        "导出Excel",
                                        id="export-btn",
                                        color="primary",
                                        className="mt-3",
                                    ),
                                ]
                            ),
                        ]
                    )
                ]
            )
        ),
    ],
    fluid=True,
)

# 样式定义
upload_style = {
    "width": "100%",
    "height": "60px",
    "lineHeight": "60px",
    "borderWidth": "1px",
    "borderStyle": "dashed",
    "borderRadius": "5px",
    "textAlign": "center",
}


# 回调处理
@app.callback(
    [
        Output("input-analysis-result", "children"),
        Output("job-results-grid", "rowData"),
    ],
    [Input("user-input", "value"), Input("upload-resume", "contents")],
    [State("upload-resume", "filename")],
)
def analyze_and_match(text_input, resume_content, resume_filename):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    # 初始化用户画像
    user_profile = {
        "user_id": "session_" + str(datetime.now().timestamp()),
        "skills": [],
        "work_experience": [],
    }

    # 文本分析
    if text_input:
        query_analysis = user_agent.analyze_query(text_input)
        user_profile.update(query_analysis)

    # 简历解析
    if resume_content:
        content_type, content_string = resume_content.split(",")
        decoded = base64.b64decode(content_string)
        with open("temp_resume.pdf", "wb") as f:
            f.write(decoded)
        resume_analysis = user_agent.analyze_resume("temp_resume.pdf")
        user_profile.update(resume_analysis)

    # 职位匹配
    matched_jobs = job_agent.match_jobs(user_profile)
    df = pd.DataFrame(matched_jobs)

    # 生成分析结果提示
    analysis_msg = []
    if text_input:
        analysis_msg.append(html.P(f"✅ 已分析求职意向：{text_input}"))
    if resume_content:
        analysis_msg.append(html.P(f"✅ 已解析简历：{resume_filename}"))

    return analysis_msg, df.to_dict("records")


# 导出功能
@app.callback(Output("export-btn", "href"), Input("job-results-grid", "rowData"))
def export_to_excel(rows):
    if not rows:
        raise dash.exceptions.PreventUpdate
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    excel_data = base64.b64encode(output.getvalue()).decode()
    return f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_data}"


if __name__ == "__main__":
    app.run_server(debug=True)
