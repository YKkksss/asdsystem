import { defineStore } from "pinia"
import { computed, ref } from "vue"

export const useAppStore = defineStore("app", () => {
  const appTitle = ref(import.meta.env.VITE_APP_TITLE || "岚仓档案数字化与流转系统")
  const stageTitle = ref("主线模块完成阶段")
  const pageDescription = ref("当前已补齐报表统计与导出能力，下一步进入已有模块补全、联调和验收收口。")

  const titleWithStage = computed(() => `${appTitle.value} · ${stageTitle.value}`)

  return {
    appTitle,
    stageTitle,
    pageDescription,
    titleWithStage,
  }
})
