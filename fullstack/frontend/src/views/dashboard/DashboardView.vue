<template>
  <section class="dashboard">
    <a-spin :spinning="loading">
      <div class="dashboard-stack">
        <header class="hero section-panel">
          <div class="hero-copy">
            <p class="eyebrow">业务工作台</p>
            <h2>{{ dashboard.headline }}</h2>
            <p class="summary">{{ dashboard.subtitle }}</p>

            <div class="hero-tags">
              <a-tag color="processing">快捷入口 {{ quickActions.length }}</a-tag>
              <a-tag v-if="dashboard.priority_focus" :color="resolveToneTagColor(dashboard.priority_focus.tone)">
                当前焦点 {{ dashboard.priority_focus.label }}
              </a-tag>
            </div>
          </div>

          <div class="hero-side">
            <a-button type="primary" :loading="loading" @click="loadDashboard">刷新概览</a-button>

            <button
              class="hero-priority-card"
              :class="dashboard.priority_focus ? `tone-${dashboard.priority_focus.tone}` : ''"
              type="button"
              @click="openRoute(dashboard.priority_focus?.route_path || null)"
            >
              <span>当前首要任务</span>
              <strong>{{ dashboard.priority_focus?.label || "暂无高优先待办" }}</strong>
              <em>{{ dashboard.priority_focus?.value ?? 0 }}</em>
              <small>{{ dashboard.priority_focus?.caption || "当前待办已经清空，可继续查看流程看板和监督信号。" }}</small>
            </button>
          </div>
        </header>

        <a-alert
          v-if="loadError"
          show-icon
          type="warning"
          class="page-alert"
          :message="loadError"
        />

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>核心指标</strong>
              <p>先看当前账号职责范围内的档案、借阅和通知总览。</p>
            </div>
          </div>

          <div class="card-grid">
            <button
              v-for="item in dashboard.summary_cards"
              :key="item.key"
              class="data-card"
              :class="`tone-${item.tone}`"
              type="button"
              @click="openRoute(item.route_path)"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.caption }}</small>
            </button>
          </div>
        </section>

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>待办提醒</strong>
              <p>优先处理当前最容易阻塞业务链路的任务。</p>
            </div>
          </div>

          <div class="card-grid">
            <button
              v-for="item in dashboard.todo_cards"
              :key="item.key"
              class="data-card data-card-todo"
              :class="`tone-${item.tone}`"
              type="button"
              @click="openRoute(item.route_path)"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.caption }}</small>
            </button>
          </div>
        </section>

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>业务动态</strong>
              <p>把当前账号最需要处理的业务单据和最近消息收敛在一起，减少反复切页查找。</p>
            </div>
          </div>

          <div class="board-grid">
            <article class="list-board">
              <div class="list-board-head">
                <strong>近期待办明细</strong>
                <p>直接进入当前最需要处理的业务入口，优先清理阻塞项。</p>
              </div>

              <div v-if="dashboard.pending_task_items.length" class="list-stack">
                <button
                  v-for="item in dashboard.pending_task_items"
                  :key="item.key"
                  class="list-item"
                  :class="`tone-${item.tone}`"
                  type="button"
                  @click="openRoute(item.route_path)"
                >
                  <div class="list-item-top">
                    <a-tag v-if="item.badge" :color="resolveToneTagColor(item.tone)">
                      {{ item.badge }}
                    </a-tag>
                    <span class="list-item-meta">{{ item.meta }}</span>
                  </div>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.description }}</p>
                </button>
              </div>

              <a-empty v-else description="当前没有待处理业务单据" />
            </article>

            <article class="list-board">
              <div class="list-board-head">
                <strong>最近通知</strong>
                <p>优先查看最新的审批、催还和系统消息，避免遗漏业务提醒。</p>
              </div>

              <div v-if="dashboard.recent_notifications.length" class="list-stack">
                <button
                  v-for="item in dashboard.recent_notifications"
                  :key="item.key"
                  class="list-item"
                  :class="`tone-${item.tone}`"
                  type="button"
                  @click="openRoute(item.route_path)"
                >
                  <div class="list-item-top">
                    <a-tag v-if="item.badge" :color="resolveToneTagColor(item.tone)">
                      {{ item.badge }}
                    </a-tag>
                    <span class="list-item-meta">{{ item.meta }}</span>
                  </div>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.description }}</p>
                </button>
              </div>

              <a-empty v-else description="最近没有新的通知消息" />
            </article>
          </div>
        </section>

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>近 7 天趋势</strong>
              <p>按借阅申请、完成归还和超期在借三个维度查看最近一周的业务变化。</p>
            </div>
          </div>

          <div class="trend-grid">
            <article
              v-for="section in dashboard.trend_sections"
              :key="section.key"
              class="trend-card"
            >
              <div class="trend-head">
                <strong>{{ section.title }}</strong>
                <p>{{ section.description }}</p>
              </div>

              <div class="trend-chart">
                <div
                  v-for="item in section.items"
                  :key="`${section.key}-${item.label}`"
                  class="trend-bar-item"
                >
                  <span class="trend-bar-value">{{ item.value }}</span>
                  <div class="trend-bar-track">
                    <span
                      class="trend-bar-fill"
                      :class="`tone-${item.tone}`"
                      :style="{ height: `${resolveTrendBarHeight(section.items, item.value)}%` }"
                    />
                  </div>
                  <strong>{{ item.label }}</strong>
                  <small>{{ item.caption }}</small>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>快捷入口</strong>
              <p>按当前角色能进入的高频页面收敛为一组操作入口。</p>
            </div>
          </div>

          <div class="quick-grid">
            <button
              v-for="item in quickActions"
              :key="item.key"
              class="quick-card"
              type="button"
              @click="openRoute(item.path)"
            >
              <strong>{{ item.name }}</strong>
              <span>{{ item.caption }}</span>
            </button>
          </div>
        </section>

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>流程看板</strong>
              <p>按档案、借阅、销毁与监督流程分区查看积压点和当前闭环状态。</p>
            </div>
          </div>

          <div class="workflow-grid">
            <article
              v-for="section in dashboard.workflow_sections"
              :key="section.key"
              class="workflow-card"
            >
              <div class="workflow-head">
                <strong>{{ section.title }}</strong>
                <p>{{ section.description }}</p>
              </div>

              <div class="workflow-item-grid">
                <button
                  v-for="item in section.items"
                  :key="item.key"
                  class="workflow-item"
                  :class="`tone-${item.tone}`"
                  type="button"
                  @click="openRoute(item.route_path)"
                >
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <small>{{ item.caption }}</small>
                </button>
              </div>
            </article>
          </div>
        </section>

        <section class="dashboard-section section-panel">
          <div class="section-head">
            <div>
              <strong>监督信号</strong>
              <p>把利用率、通知积压、超期与风险信号集中展示，便于判断当天是否存在异常。</p>
            </div>
          </div>

          <div class="signal-grid">
            <button
              v-for="item in dashboard.signal_cards"
              :key="item.key"
              class="signal-card"
              :class="`tone-${item.tone}`"
              type="button"
              @click="openRoute(item.route_path)"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.caption }}</small>
            </button>
          </div>
        </section>
      </div>
    </a-spin>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { message } from "ant-design-vue"
import { useRouter } from "vue-router"

import { fetchSystemDashboard, type SystemDashboardPayload } from "@/api/system"
import { dashboardQuickActionKeys, flattenNavigationItems, navigationEntries } from "@/config/navigation"
import { useAuthStore } from "@/stores/auth"
import { profileHasAccess } from "@/utils/access"

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const loadError = ref("")
const dashboard = reactive<SystemDashboardPayload>({
  headline: "业务工作台",
  subtitle: "按当前职责查看档案、借阅、通知与待办概览。",
  priority_focus: null,
  summary_cards: [],
  todo_cards: [],
  workflow_sections: [],
  trend_sections: [],
  signal_cards: [],
  pending_task_items: [],
  recent_notifications: [],
})

const quickActions = computed(() => {
  const quickActionMap = new Map(
    flattenNavigationItems(navigationEntries)
      .filter((item) => item.quickAction && profileHasAccess(authStore.profile, item))
      .map((item) => [item.key, item]),
  )

  return dashboardQuickActionKeys
    .map((key) => quickActionMap.get(key))
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
})

function resolveToneTagColor(tone: string) {
  if (tone === "danger") {
    return "error"
  }
  if (tone === "warning") {
    return "warning"
  }
  if (tone === "success") {
    return "success"
  }
  return "processing"
}

function resolveTrendBarHeight(items: SystemDashboardPayload["trend_sections"][number]["items"], value: number) {
  const maxValue = Math.max(...items.map((item) => item.value), 0)
  if (maxValue <= 0) {
    return 8
  }
  return Math.max(Math.round((value / maxValue) * 100), value > 0 ? 18 : 8)
}

async function loadDashboard() {
  loading.value = true
  loadError.value = ""
  try {
    const response = await fetchSystemDashboard()
    dashboard.headline = response.data.headline
    dashboard.subtitle = response.data.subtitle
    dashboard.priority_focus = response.data.priority_focus
    dashboard.summary_cards = response.data.summary_cards
    dashboard.todo_cards = response.data.todo_cards
    dashboard.workflow_sections = response.data.workflow_sections
    dashboard.trend_sections = response.data.trend_sections
    dashboard.signal_cards = response.data.signal_cards
    dashboard.pending_task_items = response.data.pending_task_items
    dashboard.recent_notifications = response.data.recent_notifications
  } catch (error) {
    loadError.value = "加载工作台概览失败，当前展示的是默认引导信息。"
    const response = error as { response?: { data?: { message?: string } } }
    message.error(response?.response?.data?.message || "加载工作台概览失败。")
  } finally {
    loading.value = false
  }
}

function openRoute(path: string | null) {
  if (!path) {
    return
  }
  void router.push(path)
}

onMounted(() => {
  void loadDashboard()
})
</script>

<style scoped>
.dashboard {
  min-height: 100%;
}

.dashboard-stack {
  display: grid;
  gap: 18px;
}

.section-panel {
  border: 1px solid rgba(10, 113, 82, 0.1);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.05);
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  background:
    radial-gradient(circle at top right, rgba(10, 113, 82, 0.16), transparent 36%),
    linear-gradient(135deg, #ffffff 0%, #f1f8f3 100%);
}

.hero-copy {
  display: grid;
  gap: 14px;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-side {
  display: grid;
  gap: 16px;
  align-content: start;
  min-width: 220px;
}

.hero-priority-card,
.data-card,
.quick-card,
.workflow-item,
.signal-card,
.list-item {
  appearance: none;
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.hero-priority-card {
  display: grid;
  gap: 8px;
  padding: 20px;
  border-radius: 20px;
  border: 1px solid rgba(10, 113, 82, 0.18);
  background: rgba(255, 255, 255, 0.95);
  color: #101828;
}

.hero-priority-card:hover,
.data-card:hover,
.quick-card:hover,
.workflow-item:hover,
.signal-card:hover,
.list-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(14, 53, 42, 0.08);
}

.hero-priority-card em {
  font-style: normal;
  font-size: 30px;
  line-height: 1.1;
}

.hero-priority-card small {
  color: #475467;
  line-height: 1.7;
}

.hero-priority-card.tone-danger {
  border-color: rgba(211, 47, 47, 0.24);
  background: linear-gradient(180deg, rgba(254, 242, 242, 0.96) 0%, #ffffff 100%);
}

.hero-priority-card.tone-warning {
  border-color: rgba(214, 120, 0, 0.24);
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.96) 0%, #ffffff 100%);
}

.hero-priority-card.tone-success {
  border-color: rgba(56, 142, 60, 0.24);
  background: linear-gradient(180deg, rgba(240, 253, 244, 0.96) 0%, #ffffff 100%);
}

.hero-priority-card.tone-default,
.hero-priority-card.tone-primary {
  border-color: rgba(10, 113, 82, 0.24);
  background: linear-gradient(180deg, rgba(241, 248, 243, 0.96) 0%, #ffffff 100%);
}

.eyebrow {
  margin: 0;
  color: #0a7152;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.hero h2 {
  margin: 0;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.2;
}

.summary {
  max-width: 720px;
  margin: 0;
  color: #475467;
  line-height: 1.8;
}

.page-alert {
  border-radius: 18px;
}

.dashboard-section {
  display: grid;
  gap: 18px;
  padding: 22px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-end;
}

.section-head strong,
.list-board-head strong {
  display: block;
  margin-bottom: 6px;
  font-size: 18px;
}

.section-head p,
.list-board-head p,
.workflow-head p,
.list-item p,
.data-card small,
.quick-card span,
.workflow-item small,
.signal-card small {
  margin: 0;
  color: #667085;
  line-height: 1.7;
}

.card-grid,
.quick-grid,
.workflow-grid,
.signal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.data-card,
.quick-card,
.workflow-card,
.workflow-item,
.signal-card,
.list-board,
.list-item {
  border: 1px solid rgba(10, 113, 82, 0.1);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.94);
}

.data-card,
.quick-card,
.workflow-item,
.signal-card {
  padding: 20px;
}

.data-card span,
.quick-card strong,
.workflow-card strong,
.workflow-item span,
.signal-card span {
  display: block;
  margin-bottom: 10px;
}

.data-card strong,
.workflow-item strong,
.signal-card strong {
  display: block;
  margin-bottom: 12px;
  font-size: 30px;
}

.data-card.tone-primary,
.data-card.tone-warning,
.data-card.tone-danger,
.data-card.tone-success,
.workflow-item.tone-primary,
.workflow-item.tone-warning,
.workflow-item.tone-danger,
.workflow-item.tone-success,
.signal-card.tone-primary,
.signal-card.tone-warning,
.signal-card.tone-danger,
.signal-card.tone-success,
.list-item.tone-primary,
.list-item.tone-warning,
.list-item.tone-danger,
.list-item.tone-success {
  border-width: 2px;
}

.data-card.tone-primary,
.workflow-item.tone-primary,
.signal-card.tone-primary,
.list-item.tone-primary {
  border-color: rgba(10, 113, 82, 0.26);
}

.data-card.tone-warning,
.workflow-item.tone-warning,
.signal-card.tone-warning,
.list-item.tone-warning {
  border-color: rgba(214, 120, 0, 0.26);
}

.data-card.tone-danger,
.workflow-item.tone-danger,
.signal-card.tone-danger,
.list-item.tone-danger {
  border-color: rgba(211, 47, 47, 0.26);
}

.data-card.tone-success,
.workflow-item.tone-success,
.signal-card.tone-success,
.list-item.tone-success {
  border-color: rgba(56, 142, 60, 0.26);
}

.data-card-todo {
  background: linear-gradient(180deg, rgba(241, 248, 243, 0.9) 0%, #ffffff 100%);
}

.quick-card {
  min-height: 132px;
}

.quick-card strong {
  font-size: 18px;
}

.board-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.list-board {
  display: grid;
  gap: 14px;
  padding: 18px;
  background: linear-gradient(180deg, rgba(246, 250, 247, 0.95) 0%, #ffffff 100%);
}

.list-board-head {
  display: grid;
  gap: 4px;
}

.list-stack {
  display: grid;
  gap: 12px;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.trend-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid rgba(10, 113, 82, 0.1);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(246, 250, 247, 0.95) 0%, #ffffff 100%);
}

.trend-head {
  display: grid;
  gap: 6px;
}

.trend-head strong {
  display: block;
  font-size: 18px;
}

.trend-head p,
.trend-bar-item small {
  margin: 0;
  color: #667085;
  line-height: 1.6;
}

.trend-chart {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
}

.trend-bar-item {
  display: grid;
  gap: 8px;
  align-items: end;
  justify-items: center;
}

.trend-bar-value {
  color: #101828;
  font-size: 14px;
  font-weight: 700;
}

.trend-bar-track {
  display: flex;
  align-items: end;
  width: 100%;
  min-height: 132px;
  padding: 8px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(240, 247, 243, 0.92) 0%, rgba(248, 250, 252, 0.92) 100%);
}

.trend-bar-fill {
  display: block;
  width: 100%;
  min-height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.4);
  transition: height 0.2s ease;
}

.trend-bar-fill.tone-primary {
  background: linear-gradient(180deg, #0a7152 0%, #28a97a 100%);
}

.trend-bar-fill.tone-success {
  background: linear-gradient(180deg, #15803d 0%, #4ade80 100%);
}

.trend-bar-fill.tone-danger {
  background: linear-gradient(180deg, #b42318 0%, #f04438 100%);
}

.trend-bar-fill.tone-warning {
  background: linear-gradient(180deg, #b54708 0%, #f79009 100%);
}

.trend-bar-fill.tone-default {
  background: linear-gradient(180deg, #94a3b8 0%, #cbd5e1 100%);
}

.trend-bar-item strong {
  color: #101828;
  font-size: 13px;
}

.trend-bar-item small {
  text-align: center;
  font-size: 12px;
}

.list-item {
  display: grid;
  gap: 10px;
  padding: 16px 18px;
}

.list-item-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.list-item strong {
  color: #101828;
  font-size: 16px;
}

.list-item-meta {
  color: #667085;
  font-size: 13px;
  white-space: nowrap;
}

.list-item p {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.workflow-card {
  display: grid;
  gap: 18px;
  padding: 18px;
  background: linear-gradient(180deg, rgba(247, 250, 248, 0.95) 0%, #ffffff 100%);
}

.workflow-head {
  display: grid;
  gap: 6px;
}

.workflow-item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

@media (max-width: 960px) {
  .hero {
    flex-direction: column;
  }

  .hero-side {
    min-width: 0;
  }
}

@media (max-width: 640px) {
  .dashboard {
    gap: 16px;
  }

  .hero,
  .dashboard-section {
    padding: 18px;
  }

  .list-item-top {
    align-items: flex-start;
    flex-direction: column;
  }

  .list-item-meta {
    white-space: normal;
  }

  .trend-chart {
    gap: 8px;
  }

  .trend-bar-track {
    min-height: 108px;
    padding: 6px;
  }
}
</style>
