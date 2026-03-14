# 初始化账号清单

> 该文件由 `bootstrap_system` 初始化命令生成，请勿在生产环境直接使用以下默认密码。

- 根部门：总部
- 账号数量：4

| 角色 | 用户名 | 密码 | 部门编码 | 说明 |
| --- | --- | --- | --- | --- |
| 管理员 | admin | Admin12345 | ROOT | 系统初始化管理员账号，负责系统配置与审批兜底。 |
| 档案员 | archivist | Archivist12345 | ARC | 档案管理、扫描任务、出入库与销毁流程使用。 |
| 借阅人 | borrower | Borrower12345 | BUS | 借阅申请、归还、通知查看等普通业务使用。 |
| 审计员 | auditor | Auditor12345 | AUD | 审计日志与报表查看使用。 |

## 使用说明

- 初始化命令可重复执行，重复执行会同步更新上述账号密码与角色绑定。
- 如果需要修改默认账号，请调整 `fullstack/backend/apps/accounts/bootstrap_defaults.py` 后重新执行初始化命令。
