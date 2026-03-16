import { defineStore } from "pinia"
import { computed, ref } from "vue"

export const useAppStore = defineStore("app", () => {
  const appTitle = ref(import.meta.env.VITE_APP_TITLE || "岚仓档案数字化与流转系统")
  const stageTitle = ref("业务工作台")
  const pageDescription = ref("按角色查看待办、统计概览、流程入口和系统消息。")

  const titleWithStage = computed(() => `${appTitle.value} · ${stageTitle.value}`)

  return {
    appTitle,
    stageTitle,
    pageDescription,
    titleWithStage,
  }
})
