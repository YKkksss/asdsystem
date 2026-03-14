<template>
  <section class="dashboard">
    <header class="hero">
      <div>
        <p class="eyebrow">项目现状</p>
        <h2>主线业务模块已全部接入，系统进入补全、联调与验收收口阶段</h2>
        <p class="summary">
          当前版本已经完成账户与角色、组织架构、审批负责人、登录失败锁定、档案主数据、实体位置、条码二维码、扫描任务、文件上传、缩略图生成、PDF 文本提取、组合检索与后端密级脱敏、借阅申请审批闭环、超期催还扫描、站内通知与邮件任务、销毁申请审批执行闭环、关键操作审计日志、文件在线预览水印、下载二次确认留痕、报表统计与 CSV 导出，以及系统管理总览页。后续将转入已有模块补全、联调验收与文档完善阶段。
        </p>
      </div>

      <div class="status-card">
        <strong>当前阶段</strong>
        <span>主线模块完成</span>
      </div>
    </header>

    <div class="metric-grid">
      <article v-for="item in metrics" :key="item.label" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.caption }}</small>
      </article>
    </div>

    <div class="roadmap-grid">
      <article v-for="item in roadmap" :key="item.title" class="roadmap-card">
        <h3>{{ item.title }}</h3>
        <p>{{ item.description }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
const metrics = [
  { label: "后端状态", value: "主线模块已齐备", caption: "含报表统计、导出、审计与风控能力" },
  { label: "前端状态", value: "已补齐系统管理", caption: "管理员可维护用户、角色、组织与系统健康" },
  { label: "运行方式", value: "支持 uv 本地开发", caption: "基础设施可通过容器辅助启动" },
]

const roadmap = [
  {
    title: "模块补全",
    description: "针对已交付模块补齐边界场景、异常提示、联动细节与文档说明。",
  },
  {
    title: "联调验收",
    description: "围绕前后端接口、角色权限和业务闭环执行系统性联调与回归测试。",
  },
  {
    title: "交付文档",
    description: "继续整理启动说明、验证步骤、问题记录和阶段性交付文档。",
  },
]
</script>

<style scoped>
.dashboard {
  display: grid;
  gap: 24px;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(10, 113, 82, 0.14), transparent 36%),
    linear-gradient(135deg, #ffffff 0%, #f1f8f3 100%);
}

.eyebrow {
  margin: 0 0 12px;
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
  margin-top: 14px;
  color: #475467;
  line-height: 1.8;
}

.status-card {
  min-width: 180px;
  display: grid;
  gap: 8px;
  align-self: flex-start;
  padding: 20px;
  border-radius: 20px;
  background: #0a7152;
  color: #ffffff;
}

.metric-grid,
.roadmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.metric-card,
.roadmap-card {
  padding: 22px;
  border: 1px solid rgba(10, 113, 82, 0.1);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
}

.metric-card span,
.roadmap-card h3 {
  display: block;
  margin-bottom: 10px;
}

.metric-card strong {
  font-size: 24px;
}

.metric-card small,
.roadmap-card p {
  color: #475467;
  line-height: 1.7;
}

.roadmap-card h3 {
  margin: 0 0 10px;
  font-size: 18px;
}

.roadmap-card p {
  margin: 0;
}

@media (max-width: 960px) {
  .hero {
    flex-direction: column;
  }

  .status-card {
    min-width: auto;
  }
}
</style>
