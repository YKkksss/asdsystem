<template>
  <section class="print-page">
    <div class="screen-toolbar">
      <div class="toolbar-copy">
        <h1>档案标签打印</h1>
        <p>进入页面后会先写入打印留痕，再自动调起浏览器打印。</p>
      </div>

      <a-space wrap>
        <a-button @click="handleBackToList">返回档案检索</a-button>
        <a-button type="primary" :loading="loading" @click="handleReprint">
          重新打印
        </a-button>
      </a-space>
    </div>

    <a-alert
      v-if="errorMessage"
      show-icon
      type="error"
      class="screen-toolbar"
      :message="errorMessage"
    />

    <a-spin :spinning="loading">
      <template v-if="printArchives.length">
        <section class="screen-summary">
          <a-card :bordered="false" class="summary-card">
            <span>打印档案数</span>
            <strong>{{ printArchives.length }}</strong>
            <small>本次打印档案的主数据与标签内容已完成留痕。</small>
          </a-card>
          <a-card :bordered="false" class="summary-card">
            <span>标签总数</span>
            <strong>{{ totalBarcodeCount }}</strong>
            <small>默认同时输出条码与二维码标签。</small>
          </a-card>
          <a-card :bordered="false" class="summary-card">
            <span>打印时间</span>
            <strong>{{ printedAtText }}</strong>
            <small>若需再次打印，可点击页面右上角“重新打印”。</small>
          </a-card>
        </section>

        <section class="print-sheet">
          <article v-for="archive in printArchives" :key="archive.id" class="archive-sheet">
            <header class="archive-header">
              <div>
                <h2>{{ archive.title }}</h2>
                <p>档号：{{ archive.archive_code }}</p>
              </div>
              <div class="archive-meta">
                <span>年度：{{ archive.year }}</span>
                <span>保管期限：{{ archive.retention_period }}</span>
                <span>状态：{{ statusLabelMap[archive.status] || archive.status }}</span>
              </div>
            </header>

            <section class="barcode-grid">
              <article v-for="barcode in archive.barcodes" :key="barcode.id" class="barcode-card">
                <strong>{{ barcode.code_type === "BARCODE" ? "条码标签" : "二维码标签" }}</strong>
                <a-image
                  v-if="barcode.image_path"
                  :src="buildArchiveAssetUrl(barcode.image_path)"
                  :preview="false"
                  class="barcode-image"
                />
                <span class="barcode-content">{{ barcode.code_content }}</span>
                <small>已打印 {{ barcode.print_count }} 次</small>
                <small>最后打印：{{ formatDateTime(barcode.last_printed_at) }}</small>
              </article>
            </section>
          </article>
        </section>
      </template>

      <a-empty
        v-else-if="!loading"
        description="未获取到可打印的档案标签，请返回列表重新选择。"
      />
    </a-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { type LocationQueryValue, useRoute, useRouter } from "vue-router"

import {
  batchPrintArchiveCodes,
  buildArchiveAssetUrl,
  type ArchiveRecordDetail,
} from "@/api/archives"

const route = useRoute()
const router = useRouter()

const statusLabelMap: Record<string, string> = {
  DRAFT: "草稿",
  PENDING_SCAN: "待扫描",
  PENDING_CATALOG: "待编目",
  ON_SHELF: "已上架",
  BORROWED: "借出中",
  DESTROY_PENDING: "销毁审批中",
  DESTROYED: "已销毁",
  FROZEN: "冻结",
}

const loading = ref(false)
const errorMessage = ref("")
const printArchives = ref<ArchiveRecordDetail[]>([])
const printedAtText = ref("-")
const lastPrintedArchiveIds = ref<number[]>([])
let printTimer: ReturnType<typeof window.setTimeout> | null = null

const totalBarcodeCount = computed(() =>
  printArchives.value.reduce((total, archive) => total + archive.barcodes.length, 0),
)

function parseArchiveIds(value: LocationQueryValue | LocationQueryValue[] | null | undefined) {
  const rawValues = Array.isArray(value) ? value : value ? [value] : []
  const mergedValues = rawValues.flatMap((item) => String(item).split(","))
  const orderedIds: number[] = []
  const seenIds = new Set<number>()

  for (const rawValue of mergedValues) {
    const archiveId = Number(rawValue)
    if (!Number.isInteger(archiveId) || archiveId <= 0 || seenIds.has(archiveId)) {
      continue
    }
    seenIds.add(archiveId)
    orderedIds.push(archiveId)
  }

  return orderedIds
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { message?: string } } }).response
    const resolvedMessage = response?.data?.message || fallbackMessage
    errorMessage.value = resolvedMessage
    message.error(resolvedMessage)
    return
  }

  errorMessage.value = fallbackMessage
  message.error(fallbackMessage)
}

async function loadPrintableArchives() {
  const archiveIds = parseArchiveIds(route.query.archiveIds)
  lastPrintedArchiveIds.value = archiveIds
  if (!archiveIds.length) {
    errorMessage.value = "缺少可打印的档案 ID，请返回档案检索页重新选择。"
    printArchives.value = []
    return
  }

  loading.value = true
  errorMessage.value = ""
  try {
    const response = await batchPrintArchiveCodes(archiveIds)
    printArchives.value = response.data
    printedAtText.value = new Date().toLocaleString("zh-CN", { hour12: false })
    await nextTick()
    triggerBrowserPrint()
    message.success(response.message)
  } catch (error) {
    printArchives.value = []
    handleRequestError(error, "加载打印档案失败。")
  } finally {
    loading.value = false
  }
}

function triggerBrowserPrint() {
  if (printTimer) {
    window.clearTimeout(printTimer)
  }
  printTimer = window.setTimeout(() => {
    window.print()
  }, 360)
}

function handleBackToList() {
  void router.push("/archives/records")
}

function handleReprint() {
  if (!lastPrintedArchiveIds.value.length) {
    message.warning("当前没有可重新打印的档案。")
    return
  }
  void loadPrintableArchives()
}

watch(
  () => route.query.archiveIds,
  () => {
    void loadPrintableArchives()
  },
  { immediate: true },
)
</script>

<style scoped>
.print-page {
  min-height: 100vh;
  padding: 28px 32px 48px;
  background:
    radial-gradient(circle at top left, rgba(10, 113, 82, 0.08), transparent 34%),
    linear-gradient(180deg, #f5f8f6 0%, #edf4f0 100%);
}

.screen-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar-copy h1 {
  margin: 0 0 8px;
  font-size: 30px;
  color: #114b3d;
}

.toolbar-copy p {
  margin: 0;
  color: #667085;
}

.screen-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.summary-card {
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(239, 247, 242, 0.94));
  box-shadow: 0 16px 38px rgba(17, 75, 61, 0.08);
}

.summary-card :deep(.ant-card-body) {
  display: grid;
  gap: 8px;
}

.summary-card span,
.summary-card small {
  color: #667085;
}

.summary-card strong {
  font-size: 28px;
  color: #0a7152;
}

.print-sheet {
  display: grid;
  gap: 20px;
}

.archive-sheet {
  break-inside: avoid;
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 20px 48px rgba(17, 75, 61, 0.08);
}

.archive-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding-bottom: 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid rgba(10, 113, 82, 0.12);
}

.archive-header h2 {
  margin: 0 0 10px;
  font-size: 24px;
  color: #114b3d;
}

.archive-header p {
  margin: 0;
  color: #667085;
}

.archive-meta {
  display: grid;
  gap: 8px;
  min-width: 180px;
  color: #475467;
  font-size: 14px;
  text-align: right;
}

.barcode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.barcode-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  border: 1px solid rgba(10, 113, 82, 0.12);
  border-radius: 20px;
}

.barcode-image :deep(img) {
  width: 100%;
  max-height: 220px;
  object-fit: contain;
}

.barcode-content {
  font-size: 15px;
  font-weight: 600;
  word-break: break-all;
}

.barcode-card small {
  color: #667085;
  font-size: 12px;
}

@media (max-width: 900px) {
  .print-page {
    padding: 20px 18px 32px;
  }

  .screen-toolbar,
  .archive-header {
    flex-direction: column;
    align-items: stretch;
  }

  .archive-meta {
    text-align: left;
  }
}

@media print {
  .print-page {
    padding: 0;
    background: #ffffff;
  }

  .screen-toolbar,
  .screen-summary {
    display: none;
  }

  .archive-sheet {
    padding: 16px 0 24px;
    box-shadow: none;
    border-radius: 0;
    background: #ffffff;
  }

  .archive-sheet + .archive-sheet {
    page-break-before: always;
  }

  .barcode-card {
    break-inside: avoid;
  }
}
</style>
