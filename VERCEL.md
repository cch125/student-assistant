# v0 / Vercel 部署

本仓库根目录已经是可部署的 Next.js 应用。Python、MinerU 和 RAGFlow 脚本继续用于离线采集、清洗和实验，不会在 Vercel 中常驻运行。

## 从 v0 同步

1. 在已经导入本仓库的 v0 Chat 中打开 Git 面板。
2. 选择 Sync / Pull changes，从 `main` 同步最新版。
3. 在预览中检查 `/`、`/pipeline` 和 `/settings`。
4. 点击 Publish 发布到 Vercel。

也可以直接在 Vercel Dashboard 中导入 `cch125/student-assistant`，Framework Preset 选择 Next.js，Root Directory 保持仓库根目录。

## 环境变量

文字问答、看板和知识库导入不需要在 Vercel 保存 RAGFlow 密钥；每位组员在 `/settings` 输入自己的连接。

照片问答需要管理员在 Vercel Project Settings -> Environment Variables 中配置：

```text
VLM_BASE_URL=https://api.siliconflow.cn/v1
VLM_API_KEY=重新创建的视觉模型密钥
VLM_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

不要把真实密钥写入 `.env.example`、源码或 v0 提示词。

## RAGFlow 条件

- Vercel 无法访问组员电脑上的 `localhost:8080`。
- RAGFlow 必须部署为可被 Vercel 访问的公网 HTTPS 服务。
- RAGFlow 内需要预先配置 LLM 和 Embedding 模型，并创建至少一个目标知识库。
- 推荐团队共用一套云端 RAGFlow；需要隔离实验时再使用各自实例。

## 本地验证

```powershell
pnpm install
pnpm lint
pnpm build
pnpm dev
```
