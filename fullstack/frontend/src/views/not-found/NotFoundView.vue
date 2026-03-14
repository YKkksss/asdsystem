<template>
  <section class="empty-page">
    <div class="empty-card">
      <p>404</p>
      <h1>页面不存在</h1>
      <span>当前访问的页面尚未创建或路由地址有误。</span>
      <RouterLink to="/">返回工作台</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router"
</script>

<style scoped>
.empty-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.empty-card {
  width: min(520px, 100%);
  display: grid;
  gap: 12px;
  padding: 36px;
  text-align: center;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 24px 60px rgba(12, 54, 43, 0.08);
}

.empty-card p {
  margin: 0;
  color: #0a7152;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.empty-card h1 {
  margin: 0;
}

.empty-card span {
  color: #475467;
  line-height: 1.7;
}

.empty-card a {
  width: fit-content;
  margin: 8px auto 0;
  padding: 10px 18px;
  border-radius: 999px;
  background: #0a7152;
  color: #ffffff;
}
</style>
