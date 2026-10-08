# Olist Power BI 验证记录

## 验证环境

- Power BI Desktop：2.157.879.0
- 报表：`Ecommerce-Operations-Analytics-Olist-V2`
- 数据源：`dashboard/powerbi_data/olist_*.csv`
- 数据范围：Olist 公开历史数据，金额 BRL，销售口径为原始 `delivered`

## Desktop 验证

1. 以本机 `dashboard/powerbi_data` 路径生成并打开 Olist PBIP。
2. Power BI Desktop 成功解析六张 imported mart 和 `KPI Measures`。
3. 执行刷新后，四页 visual 显示真实数据。
4. 保存为 `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Olist-V2.pbix`。
5. 关闭 PBIP 会话，并从生成的 PBIX 重新打开。
6. 重开后的“评价与订单体验”页仍显示 4.16、625、0.63% 和 16.63%，趋势及品类图表已加载。
7. 不保存重开会话产生的视图状态变化，保留最初验证后的 PBIX。

最终文件大小为 2,734,437 bytes；SHA-256 为：

```text
80CC21129401D376EB3DD72B68BDBA7BF0BA8ACF36B333C7C1AB0A39B541E1C0
```

## 页面与结构

| 页面 | Visual 数 | 页面尺寸 |
|---|---:|---|
| 经营总览 | 19 | 1440×810 |
| 商品与品类分析 | 20 | 1440×810 |
| 客户价值 | 20 | 1440×810 |
| 评价与订单体验 | 17 | 1440×810 |

PBIR 共 76 个 visual。最终静态检查中 86 个 JSON 文件均可解析。

## 指标对账

| 指标 | 报表显示/底层值 |
|---|---:|
| Merchandise GMV | BRL 13,221,498.11 |
| Orders | 96,478 |
| Purchasing Customers | 93,358 |
| AOV | BRL 137.04 |
| Repeat Purchase Rate | 3.00% |
| Average Review Score | 4.156（卡片 4.16） |
| Canceled Orders | 625 |
| Cancel Rate | 0.629%（卡片 0.63%） |
| Freight Ratio | 16.63% |

## 可移植性

Desktop 验证时临时使用本机绝对 `DataRoot`。关闭 Desktop 后，提交的 `expressions.tmdl` 已恢复为中性占位符。`.pbi/` cache、原始数据、SQLite 和生成 CSV 不进入 Git。

PBIX 内嵌验证时的数据快照，可直接打开查看；PBIP 刷新需要使用者设置自己的 `DataRoot`。

## 自动化检查

- 完整测试：`Ran 67 tests in 575.506s`，结果 `OK`。
- PBIR：4 页、76 个 visual、86 个 JSON，全部可解析。
- PowerShell：两个 Olist 生成脚本均通过 AST 语法解析。
- 文档：仓库内 Markdown 本地链接全部可解析。
- Git：`git diff --check` 无 whitespace error。
- 公开审计：未发现真实凭据、private key 或本机绝对路径；`.env.example` 仅包含占位符，MySQL 导入代码从环境变量读取凭据。

## 边界

- 截图来自真实 Desktop 页面，不是静态仿制图。
- 没有将 Synthetic 截图或 PBIX 作为 Olist 证据。
- 页面 4 不展示交付时长，因为当前 mart 不支持该指标。
- Olist 报表不含广告、商品成本、利润、毛利或模拟退款 KPI。
