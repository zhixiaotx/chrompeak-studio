import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" 让构建产物使用相对路径，方便部署到 GitHub Pages 子路径 / 任意静态目录
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 1500,
  },
  server: {
    port: 5173,
    proxy: {
      // 本地开发时把 /api 代理到 FastAPI 后端，避免跨域
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
