import path from "node:path"

import vue from "@vitejs/plugin-vue"
import { defineConfig } from "vite"
import Components from "unplugin-vue-components/vite"
import { AntDesignVueResolver } from "unplugin-vue-components/resolvers"

export default defineConfig({
  plugins: [
    vue(),
    Components({
      dts: false,
      resolvers: [
        AntDesignVueResolver({
          importStyle: false,
        }),
      ],
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined
          }

          if (id.includes("axios")) {
            return "vendor-axios"
          }

          if (
            id.includes("/vue/") ||
            id.includes("/@vue/") ||
            id.includes("vue-router") ||
            id.includes("pinia")
          ) {
            // 将框架基础运行时保持在稳定公共包中，减少业务页面重复下载。
            return "vendor-vue"
          }

          return undefined
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: ["easykitbox.com", "154.217.240.44"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/media": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
})
