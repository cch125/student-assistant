/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: false,
  },
  // 让 Serverless 打包时包含仓库中的知识库快照，供导入接口在运行时读取。
  outputFileTracingIncludes: {
    "/api/snapshot/**": ["./knowledge_base/**"],
  },
}

export default nextConfig
