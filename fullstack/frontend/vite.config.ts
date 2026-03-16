import path from "node:path"

import vue from "@vitejs/plugin-vue"
import { defineConfig, loadEnv } from "vite"
import Components from "unplugin-vue-components/vite"
import { AntDesignVueResolver } from "unplugin-vue-components/resolvers"

const DEFAULT_DEV_HOST = "127.0.0.1"
const DEFAULT_DEV_PORT = 5173
const DEFAULT_PREVIEW_PORT = 4173
const DEFAULT_ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

function resolvePort(value: string | undefined, fallbackPort: number): number {
  const parsedPort = Number(value)

  if (!Number.isInteger(parsedPort) || parsedPort <= 0) {
    return fallbackPort
  }

  return parsedPort
}

function resolveAllowedHosts(rawHosts: string | undefined): true | string[] {
  const normalizedHosts = rawHosts
    ?.split(",")
    .map((host) => host.trim())
    .filter(Boolean)

  if (!normalizedHosts || normalizedHosts.length === 0) {
    return DEFAULT_ALLOWED_HOSTS
  }

  const filteredHosts = normalizedHosts.filter((host) => host !== "*")

  if (filteredHosts.length === 0) {
    return DEFAULT_ALLOWED_HOSTS
  }

  return filteredHosts
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "")
  const devHost = env.ASD_FRONTEND_DEV_HOST?.trim() || DEFAULT_DEV_HOST
  const devPort = resolvePort(env.ASD_FRONTEND_DEV_PORT, DEFAULT_DEV_PORT)
  const previewPort = resolvePort(env.ASD_FRONTEND_PREVIEW_PORT, DEFAULT_PREVIEW_PORT)

  return {
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
      host: devHost,
      port: devPort,
      strictPort: true,
      // 开发阶段默认仅允许本机访问，避免误暴露到局域网或公网。
      allowedHosts: resolveAllowedHosts(env.ASD_FRONTEND_ALLOWED_HOSTS),
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
    preview: {
      host: devHost,
      port: previewPort,
      strictPort: true,
    },
  }
})
