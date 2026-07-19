# 暨南大学学生助手

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

## RAGFlow

项目默认连接本机 RAGFlow：

```text
http://localhost:8080
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
