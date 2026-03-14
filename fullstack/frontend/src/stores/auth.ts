import { computed, ref } from "vue"
import { defineStore } from "pinia"

import type { LoginResponse } from "@/api/auth"
import {
  clearStoredSession,
  readStoredAccessToken,
  readStoredProfile,
  readStoredRefreshToken,
  writeStoredAccessToken,
  writeStoredProfile,
  writeStoredRefreshToken,
} from "@/utils/session"

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref(readStoredAccessToken())
  const refreshToken = ref(readStoredRefreshToken())
  const profile = ref<LoginResponse["profile"] | null>(readStoredProfile<LoginResponse["profile"]>())

  const isAuthenticated = computed(() => Boolean(accessToken.value))

  function updateAccessToken(token: string | null) {
    accessToken.value = token
    writeStoredAccessToken(token)
  }

  function updateRefreshToken(token: string | null) {
    refreshToken.value = token
    writeStoredRefreshToken(token)
  }

  function updateProfile(nextProfile: LoginResponse["profile"] | null) {
    profile.value = nextProfile
    writeStoredProfile(nextProfile)
  }

  function setSession(data: LoginResponse) {
    updateAccessToken(data.tokens.access)
    updateRefreshToken(data.tokens.refresh)
    updateProfile(data.profile)
  }

  function clearSession() {
    accessToken.value = null
    refreshToken.value = null
    profile.value = null
    clearStoredSession()
  }

  return {
    accessToken,
    refreshToken,
    profile,
    isAuthenticated,
    updateAccessToken,
    updateRefreshToken,
    updateProfile,
    setSession,
    clearSession,
  }
})
