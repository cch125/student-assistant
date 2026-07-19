# 暨南大学学生助手

当前版本：`v0.9.0`。每次大更新都会同步更新 [CHANGELOG.md](CHANGELOG.md)、创建 Git 标签并推送到 GitHub，旧版本会完整保留。

这是一个面向暨南大学学生事务的 RAG 助手项目。项目目标不是只提供文档下载，而是把公开官网中的学生常用信息整理成可检索的服务卡片，让学生可以直接询问：

- 请假申请表在哪里下载？
- 学生证丢了怎么办？
- 校巴时间是什么？
- 校园网怎么申请？
- 图书怎么续借？
- 食堂几点开门？

如果知识库没有明确来源，助手会拒绝猜测，避免误导学生。

## 当前状态

已跑通第一阶段流程：

- 暨南大学公开网页采集
- 数据清洗
- 服务卡片生成
- RAGFlow 知识库导入
- 本地简约问答页面
- 未命中问题记录

当前核心服务卡片覆盖 34 个事项，包含：

- 文档下载：请假申请表、转专业申请表、复学/休学申请表等
- 办事流程：学生证补办、成绩单打印、毕业证/学位证补办等
- 信息查询：校巴时间、校历、校园网、校园卡、图书续借、食堂营业时间等
- 学生事务扩展：本科休学/复学/退学流程、研究生服务中心、就业手续入口、公费医疗服务指南等

## 目录说明

```text
cleaner/       数据清洗和服务卡片生成
multimodal/    MinerU 多模态附件清洗
crawler/       暨南大学公开网页采集
ragflow/       RAGFlow 导入、检索和测试脚本
scripts/       辅助脚本
config/        采集配置
web_app.py     本地问答页面
visualize_pipeline.py  数据流程可视化看板
```

以下目录默认不提交到 GitHub：

```text
data/raw/
data/files/
data/cleaned/
data/feedback/
outputs/
```

它们属于本地采集结果、生成物或反馈日志。

## 本地运行

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

生成服务卡片：

```powershell
python cleaner\build_service_cards.py
```

启动本地问答页面：

```powershell
python web_app.py
```

浏览器打开：

```text
http://127.0.0.1:8090
```

查看流程看板：

```powershell
python visualize_pipeline.py
```

然后打开：

```text
http://127.0.0.1:8090/pipeline
```

覆盖报告 JSON：

```text
http://127.0.0.1:8090/api/coverage
```

## MinerU 多模态清洗

项目使用独立 Python 3.12 环境运行 MinerU，不改动主项目 Python。当前机器的运行目录为：

```text
D:\student-assistant-runtime
```

环境安装命令：

```powershell
$env:UV_CACHE_DIR='D:\student-assistant-runtime\uv-cache'
$env:UV_PYTHON_INSTALL_DIR='D:\student-assistant-runtime\python'
python -m uv python install 3.12
python -m uv venv 'D:\student-assistant-runtime\mineru-venv' --python 3.12
python -m uv pip install --python 'D:\student-assistant-runtime\mineru-venv\Scripts\python.exe' -r requirements-mineru.txt
& 'D:\student-assistant-runtime\mineru-venv\Scripts\mineru-models-download.exe' --source modelscope --model_type pipeline
```

解析全部支持的附件并自动导入 RAGFlow 第一阶段综合知识库：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_mineru.ps1
```

只处理指定附件：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_mineru.ps1 -Path 'data\files\example.pdf'
```

MinerU 当前处理 PDF、图片、DOCX、PPTX、XLSX。旧 `.doc`、`.xls` 和压缩包会标记为不支持，并继续保留原 RAGFlow 解析结果。成功生成 MinerU 版本后，MinerU Markdown 负责检索；同名原始附件以不解析的方式保留在知识库文件列表中，供查看和下载，同时避免重复分块。

清洗状态、图片数量、结构化 JSON 数量和 RAGFlow 导入结果可在以下页面查看：

```text
http://127.0.0.1:8090/pipeline
```

MinerU 模型和运行环境不提交 GitHub；项目只提交可复现的安装说明和处理代码。

## RAGFlow

项目默认连接本机 RAGFlow：

```text
http://localhost:8080
```

### 数据流水线与分块对照实验

先运行 MinerU 后的二次清洗：

```powershell
python multimodal\postprocess_mineru.py
```

创建或更新 A/B/C 数据流水线知识库，上传同一份清洗语料并解析：

```powershell
python ragflow\import_experiment_pipelines.py
```

解析完成后运行固定问题检索对照：

```powershell
python ragflow\evaluate_chunk_experiments.py
```

使用 30 个可回答问题和 10 个应拒答问题自动搜索知识库、向量权重与相似度阈值：

```powershell
python ragflow\tune_retrieval_parameters.py --workers 4
```

已经完成 API 检索时，可以复用原始结果重新评分，并把最优配置写入项目：

```powershell
python ragflow\tune_retrieval_parameters.py --reuse-results --apply
```

推荐参数保存在 `config/recommended_retrieval.json`，完整 JSON/Markdown 报告生成在 `outputs` 目录。RAGFlow 的知识库更新接口不接受检索权重和阈值，因此应用在每次检索请求中传入这些参数，不修改知识库本身。

三套知识库分别使用 500 tokens/10% 重叠、800 tokens/10% 重叠、1200 tokens/15% 重叠。它们绑定真实的 RAGFlow 数据流水线，因此文件完成解析后会在知识库“日志”页生成记录。实验结果和入口也会显示在：

```text
http://127.0.0.1:8090/pipeline
```

核心知识库名称：

```text
暨南大学学生助手-核心服务卡片
```

导入核心服务卡片：

```powershell
python ragflow\import_core_services.py
```

刷新重导：

```powershell
$env:RAGFLOW_REFRESH_CORE='1'
python ragflow\import_core_services.py
Remove-Item Env:\RAGFLOW_REFRESH_CORE
```

命令行测试：

```powershell
python ragflow\ask_core_services.py "校巴时间"
```

## 安全说明

- 不提交 API Key、`.env`、RAGFlow token、反馈日志或爬取原始文件。
- 只采集暨南大学公开网页，不登录教务系统、门户或网上服务大厅。
- 回答必须基于知识库来源；没有明确材料时拒答。

## 版本发布规则

大更新完成后按以下顺序发布：

1. 更新 `VERSION` 和 `CHANGELOG.md`。
2. 运行 `python scripts\check_release.py` 检查版本记录。
3. 提交代码并创建带说明的 `vX.Y.Z` Git 标签。
4. 同时推送 `main` 分支和版本标签到 GitHub。

查看历史版本：

```powershell
git tag --list
git log --oneline --decorate
```
