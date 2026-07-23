# FastAPI 本地运行说明

项目已统一为 FastAPI，不再需要 Node.js、npm、pnpm 或 Next.js。

## 一键启动

```powershell
cd "C:\Users\Andy\Desktop\最新\student-assistant-main"
powershell -ExecutionPolicy Bypass -File .\scripts\run_fastapi.ps1
```

访问 `http://127.0.0.1:8090`。

第一次访问会要求创建管理员；后续普通用户可从登录页注册。

管理员在 `/settings` 中配置 RAGFlow，配置会保存到 `.env.local` 并立即生效。

## 页面权限

- 普通用户：智能问答、图片提问、来源引用、历史记录
- 管理员：包含普通用户功能，并可访问 Agent 日志、数据看板、连接配置、用户管理

## 停止

在启动服务的 PowerShell 窗口按 `Ctrl+C`。
