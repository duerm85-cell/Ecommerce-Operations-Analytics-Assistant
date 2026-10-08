# GitHub 发布检查清单

## Olist 主版本

- [x] README 为中文优先，并明确 Olist 是公开历史数据。
- [x] ODS、DWD、customer identity bridge、Analytics marts 与 6 个 CSV 已完成。
- [x] 四页 Olist PBIR/TMDL 已生成并可由 Desktop 解析。
- [x] Olist PBIX 已刷新、保存并重新打开验证。
- [x] 四张截图来自真实 Power BI Desktop 页面。
- [x] Olist 不使用广告、成本、利润、毛利或模拟退款 KPI。
- [x] Synthetic V1.1/V1.2 仍保留并明确标为 Legacy。

## 仓库卫生

- [x] `README.md`、`LICENSE`、`docs/`、`data/`、`dashboard/`、`reports/` 与 `tests/` 存在。
- [x] `.gitignore` 排除环境、cache、原始数据、SQLite、生成 CSV 与 Power BI 本地状态。
- [x] Olist PBIP 提交版本不包含本机绝对路径。
- [x] 没有发现真实凭据或 private key。
- [x] 文档使用中性项目表述，不包含个人定位。
- [x] Markdown 本地链接可解析。
- [x] JSON、PowerShell 语法与 Git whitespace 检查通过。
- [x] 完整自动化测试 67/67 通过。

## 发布步骤

- [ ] 检查 staged allowlist 与 staged diff。
- [ ] 创建本地提交：`feat: finalize Olist Power BI presentation`。
- [ ] 仅推送 `origin feat/olist-real-data`。
- [ ] 推送后核对远端 branch SHA。

本次任务不合并 `main`，不创建 tag 或 GitHub Release，不 force-push，也不删除任何远端分支。
