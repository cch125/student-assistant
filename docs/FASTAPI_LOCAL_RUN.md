# FastAPI 本地演示与组员协作说明

本项目当前推荐使用 FastAPI 本地版进行演示。由于团队没有云服务器，RAGFlow 仍运行在每位组员自己的电脑上，学生助手通过本机配置连接本机 RAGFlow。

## 运行方式

### 方式一：Python 直接运行

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app_fastapi:app --host 127.0.0.1 --port 8090
```

打开：

```text
http://127.0.0.1:8090
```

### 方式二：Docker Compose

```powershell
docker compose -f compose.yaml up --build
```

打开：

```text
http://127.0.0.1:8090
```

## 默认演示账号

```text
账号：cch125
密码：admin123
```

这是本地演示账号。正式使用时应替换为学校统一认证，或至少修改本地 SQLite 数据库中的账号密码。

## 必要配置

复制 `.env.example` 为 `.env.local`，填写自己的 RAGFlow 和模型配置：

```text
RAGFLOW_BASE_URL=http://localhost:8080
RAGFLOW_API_KEY=你的 RAGFlow API Key
RAGFLOW_DATASET_ID=主知识库 ID
RAGFLOW_NOTICE_DATASET_ID=通知/补充知识库 ID
```

不要把 `.env.local` 上传到 GitHub。

## 页面入口

- `/`：学生问答助手
- `/agent-logs`：Agent 执行日志
- `/pipeline`：数据清洗与知识库看板
- `/settings`：连接配置状态

## 当前 Agent 链路

```text
Intent Agent
  -> Router Agent
      -> Study Place Agent / Health Agent / Retriever Agent / Tool Agent / Reject Agent
  -> Reflection Agent
  -> Answer Agent
```

系统会记录每次提问经过的节点、耗时、分数和最终决策，用于答辩展示。

## 无服务器协作方案

每位组员：

1. 从 GitHub 下载代码。
2. 本机启动 RAGFlow。
3. 导入项目提供的清洗数据或知识库快照。
4. 填写 `.env.local`。
5. 启动 FastAPI 学生助手。

这种方案不需要购买云服务器，但每台电脑都需要各自配置 RAGFlow 和 API Key。

