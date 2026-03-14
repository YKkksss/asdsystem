import { expect, test } from "@playwright/test"

import { loginByUi } from "./support"

test("管理员未登录访问系统管理时应先跳登录并在登录后回跳", async ({ page }) => {
  await page.goto("/system/management")

  await expect(page).toHaveURL(/\/login\?redirect=/)
  await page.getByPlaceholder("请输入用户名").fill("admin")
  await page.getByPlaceholder("请输入密码").fill("Admin12345")
  await page.getByRole("button", { name: "登录系统" }).click()

  await expect(page).toHaveURL(/\/system\/management$/)
  await expect(page.getByText("系统管理总览")).toBeVisible()
  await expect(page.getByRole("button", { name: "新建用户" })).toBeVisible()

  await page.getByRole("button", { name: "退出登录" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole("button", { name: "登录系统" })).toBeVisible()
})

test("借阅人不应看到系统管理菜单且访问受限页面时应回到工作台", async ({ page }) => {
  await loginByUi(page, "borrower", "Borrower12345")

  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole("link", { name: /系统管理/ })).toHaveCount(0)

  await page.goto("/system/management")

  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText("主线业务模块已全部接入，系统进入补全、联调与验收收口阶段")).toBeVisible()
})

test("审计员登录后应能访问报表中心并看到统计页标题", async ({ page }) => {
  await page.goto("/reports/center")

  await expect(page).toHaveURL(/\/login\?redirect=/)
  await page.getByPlaceholder("请输入用户名").fill("auditor")
  await page.getByPlaceholder("请输入密码").fill("Auditor12345")
  await page.getByRole("button", { name: "登录系统" }).click()

  await expect(page).toHaveURL(/\/reports\/center$/)
  await expect(page.getByRole("button", { name: "刷新报表" })).toBeVisible()
  await expect(page.getByText("部门借阅排行")).toBeVisible()
})
