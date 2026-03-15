<template>
  <div class="login-page">
    <section class="login-panel">
      <div class="hero-copy">
        <p class="eyebrow">统一身份入口</p>
        <h1>岚仓档案数字化与流转系统</h1>
        <p class="description">
          当前已接入统一登录、失败锁定、档案主数据和实体位置基础能力，可从这里进入业务工作台。
        </p>
      </div>

      <a-form
        :model="formState"
        class="login-form"
        layout="vertical"
        @finish="handleSubmit"
      >
        <a-form-item label="用户名">
          <a-input v-model:value="formState.username" placeholder="请输入用户名" size="large" />
        </a-form-item>

        <a-form-item label="密码">
          <a-input-password
            v-model:value="formState.password"
            placeholder="请输入密码"
            size="large"
          />
        </a-form-item>

        <div class="login-actions">
          <a-button :loading="submitting" block html-type="submit" size="large" type="primary">
            登录系统
          </a-button>
          <RouterLink to="/">返回工作台</RouterLink>
        </div>
      </a-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { message } from "ant-design-vue"
import { RouterLink } from "vue-router"
import { useRoute, useRouter } from "vue-router"

import { login } from "@/api/auth"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const submitting = ref(false)

const formState = reactive({
  username: "",
  password: "",
})

async function handleSubmit() {
  if (!formState.username.trim() || !formState.password.trim()) {
    message.warning("请输入用户名和密码。")
    return
  }

  submitting.value = true
  try {
    const response = await login({
      username: formState.username.trim(),
      password: formState.password,
    })
    authStore.setSession(response.data)
    message.success(response.message)
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/"
    await router.push(redirect)
  } catch (error) {
    const fallbackMessage = "登录失败，请稍后重试。"
    if (typeof error === "object" && error !== null && "response" in error) {
      const response = (error as { response?: { data?: { message?: string } } }).response
      message.error(response?.data?.message || fallbackMessage)
      return
    }
    message.error(fallbackMessage)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-panel {
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 420px);
  gap: 20px;
  padding: 28px;
  border-radius: 32px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(242, 248, 244, 0.96));
  box-shadow: 0 24px 60px rgba(12, 54, 43, 0.12);
}

.hero-copy {
  padding: 36px;
  border-radius: 24px;
  color: #f7fffb;
  background:
    radial-gradient(circle at top right, rgba(156, 241, 208, 0.28), transparent 36%),
    linear-gradient(135deg, #0d6f53 0%, #0f4d41 100%);
}

.eyebrow {
  width: fit-content;
  margin: 0 0 16px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(30px, 4vw, 48px);
  line-height: 1.15;
}

.description {
  max-width: 520px;
  margin-top: 18px;
  color: rgba(247, 255, 251, 0.82);
  line-height: 1.8;
}

.login-form {
  padding: 24px;
  border-radius: 24px;
  background: #ffffff;
}

.login-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
}

@media (max-width: 900px) {
  .login-panel {
    grid-template-columns: 1fr;
  }

  .hero-copy,
  .login-form {
    padding: 20px;
  }

  .login-actions {
    width: 100%;
  }
}
</style>
