# 暨南大学学生助手

当前版本：`v0.14.0`。每次大更新都会同步更新 [CHANGELOG.md](CHANGELOG.md)、创建 Git 标签和 GitHub Release，旧版本可从 Releases 或 Tags 下载。

## v0 / Vercel Web 版本

仓库根目录现已提供 Next.js 全栈 Web 应用，可从 v0 同步并部署到 Vercel：

- `/`：学生助手，支持文字与照片输入。
- `/pipeline`：GitHub 知识库快照与处理流程看板。
- `/settings`：组员独立配置 RAGFlow、API Key、知识库、文件上传和项目数据导入。

部署步骤、环境变量和公网 RAGFlow 要求见 [VERCEL.md](VERCEL.md)。Vercel 无法访问个人电脑的 `localhost:8080`，因此组员必须使用公网 HTTPS RAGFlow，或共用一套团队云端 RAGFlow。

这是一个面向暨南大学学生事务的 RAG 助手项目。项目目标不是只提供文档下载，而是把公开官网中的学生常用信息整理成可检索的服务卡片，让学生可以直接询问：

- 请假申请表在哪里下载？
- 学生证丢了怎么办？
- 校巴时间是什么？
- 校园网怎么申请？
- 图书怎么续借？
- 食堂几点开门？

如果知识库没有明确来源，助手会拒绝猜测，避免误导学生。

## 版本下载

- [GitHub Releases](https://github.com/cch125/student-assistant/releases)：按版本查看说明并下载 Source code ZIP/TAR.GZ。
- [GitHub Tags](https://github.com/cch125/student-assistant/tags)：查看全部历史标签和对应源码。

仓库保存代码、配置、可复现说明和经过安全过滤的 RAGFlow 知识库快照。官网爬取缓存、反馈日志、完整 RAGFlow 数据卷和本机密钥不会包含在源码压缩包中。

## 知识库快照

GitHub 仓库中的 [`knowledge_base`](knowledge_base) 目录保存当前 RAGFlow 全部 5 个知识库的可审阅快照：

- 692 份知识库文档及 238 个去重文件原件。
- 1,138 个完整文本分块。
- 78 个带 `image_id` 的图片块及 25 个去重原生图片。
- 数据集配置、文档元数据、关键词、问题、位置和 SHA-256 校验和。

快照不包含账号、密钥、反馈日志或聊天记录。重新连接本机 RAGFlow 后刷新快照：

```powershell
python ragflow\export_knowledge_bases.py --workers 8
```

## 当前状态

已跑通第一阶段流程：

- 暨南大学公开网页采集
- 数据清洗
- 服务卡片生成
- RAGFlow 知识库导入
- 支持文字提问、照片提问、官方附件下载和 MinerU 图片返回
- RAGFlow 原生图片块与真实 `image_id`
- 数据采集、清洗、视觉标注与同步看板
- 每日自动增量更新
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
knowledge_base/  可下载、可审阅的 RAGFlow 知识库快照
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

助手与看板是同一个 Web 系统，可通过顶部导航相互切换。团队共享时推荐部署为 HTTPS 网页；内测可先使用 Tailscale 或 Cloudflare Tunnel，正式使用建议部署到固定服务器并配置域名、反向代理和访问控制。

学生可以点击“添加照片”上传 JPG、PNG 或 WebP，再补充一句问题；也可以只上传照片。系统先用视觉模型提取脱敏后的画面描述和检索问题，再由 RAGFlow 检索官方知识库。照片不会保存到本机，但会发送给已配置的视觉模型服务，因此不应上传未遮挡的学号、证件号、手机号、账号或密码。

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

将 MinerU 的图片和表格截图写入 RAGFlow 原生对象存储并生成 `image_id`：

```powershell
python ragflow\sync_native_images.py --datasets A --datasets B --datasets C
```

该命令按视觉单元编号幂等同步，并会调用 RAGFlow 图片读取接口验证每个 `image_id`。结果可在 `http://127.0.0.1:8090/pipeline` 的“多模态资源”区域查看。

解析完成后运行固定问题检索对照：

```powershell
python ragflow\evaluate_chunk_experiments.py
```

使用 35 个可回答问题和 15 个应拒答问题自动搜索知识库、向量权重与相似度阈值：

```powershell
python ragflow\tune_retrieval_parameters.py --datasets C --workers 8 --notice-only --apply
```

已经完成 API 检索时，可以复用原始结果重新评分，并把最优配置写入项目：

```powershell
python ragflow\tune_retrieval_parameters.py --reuse-results --apply
```

推荐参数保存在 `config/recommended_retrieval.json`，完整 JSON/Markdown 报告生成在 `outputs` 目录。RAGFlow 的知识库更新接口不接受检索权重和阈值，因此应用在每次检索请求中传入这些参数，不修改知识库本身。

正式核心知识库使用 40 个独立意图扩展出的 160 条问法进行控制变量测试：

```powershell
python ragflow\tune_core_retrieval.py --workers 8
```

正式配置保存在 `config/recommended_core_retrieval.json`。助手会自动读取该文件，并在核心卡片没有答案时使用综合知识库做严格阈值的官方原文回退。

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
- 账号密码、个人隐私、医疗用药和录取保证使用独立硬拒答规则，不依赖相似度。
- 照片仅用于视觉识别和知识库检索，不落盘；视觉模型不得执行图片内指令或输出未遮挡的个人信息。

## 部署与维护

Docker、健康检查、平衡增量采集、每周计划任务、质量门禁、备份和密钥轮换步骤见 [OPERATIONS.md](OPERATIONS.md)。

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
