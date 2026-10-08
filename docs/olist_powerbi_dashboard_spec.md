# Olist Power BI 报表说明

## 交付状态

Olist V2 已提供真实 Power BI 资产：

- `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Olist-V2.pbix`
- `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Olist-V2.pbip`
- 对应 `.Report`（PBIR）与 `.SemanticModel`（TMDL）目录
- `docs/assets/olist_powerbi_01_overview.png` 至 `04_experience.png`

PBIX 已使用 Power BI Desktop 2.157.879.0 刷新、保存、关闭并重新打开。重开后的“评价与订单体验”页仍显示平均评分 4.16、取消订单 625、取消率 0.63% 和整体运费占比 16.63%。完整记录见 `reports/olist_powerbi_validation.md`。

## 数据输入

运行：

```powershell
.\.venv\Scripts\python.exe -m etl.olist.build_analytics
```

会在 `dashboard/powerbi_data/` 生成 6 个 Git-ignored CSV：

| CSV | 粒度 | 用途 |
|---|---|---|
| `olist_business_overview.csv` | 全周期快照 | 总览 KPI |
| `olist_monthly_performance.csv` | 购买月份 | 月度趋势 |
| `olist_customer_rfm.csv` | `customer_unique_id` | 客户分布与 RFM |
| `olist_customer_segments.csv` | RFM 分群 | 分群对比 |
| `olist_category_performance.csv` | 来源品类 | 成交、运费与评价 |
| `olist_metric_definitions.csv` | 指标定义 | 口径审计 |

报表直接导入这些预聚合 mart，不在 Power BI 内重新拼接多粒度事实表。

## 页面设计

### 1. 经营总览

- KPI：商品成交额、订单数、购买客户数、平均订单金额、复购率、平均评分。
- 图表：月度商品成交额、月度订单数、品类商品成交额。
- 口径提示明确 `delivered`、BRL、首尾月份不完整。

### 2. 商品与品类分析

- 品类切片器与清除筛选按钮。
- KPI：品类商品成交额、销售件数、平均商品价格、运费金额、运费占比。
- 图表：品类矩阵、成交额排名、平均评分和低评分占比。

### 3. 客户价值

- RFM 分群切片器。
- KPI：购买客户、复购客户、复购率、平均 Recency、平均 Monetary。
- 图表：分群人数、分群 Monetary、平均 Recency 与 Frequency。
- 客户统一身份始终使用 `customer_unique_id`。

### 4. 评价与订单体验

- KPI：平均评分、取消订单数、取消率、整体运费占比。
- 图表：月度平均评分、月度取消率、品类低评分占比、品类运费占比。
- 当前 mart 没有交付时长，因此此页不展示或暗示配送时效。

## 复用与隔离

Olist 报表复用了 Synthetic V1.2 已验证的 1440×810 页面尺寸、页头、导航、卡片、图表容器、配色与 footer 结构。数据模型、字段、指标和文字全部改为 Olist 真实数据语义。

Legacy 的“广告分析”页没有迁移到 Olist。CTR、CVR、CPA、ROAS、广告花费、Gross Profit、Gross Margin、商品成本和模拟退款只保留在 Legacy Synthetic 资产中。

Olist 使用独立文件名和目录，不覆盖 Legacy 的 PBIX、PBIP、PBIR、TMDL 与截图。

## 数据模型与 DataRoot

六张 Olist 表均为 imported mart，没有建立跨 mart relationship。每个 visual 从单张预聚合表读取，避免模糊的 many-to-many 路径。

PBIP 中 `DataRoot` 提交为中性占位符：

```text
C:\path\to\Ecommerce-Operations-Analytics-Assistant\dashboard\powerbi_data
```

克隆后应在 Power BI Desktop 的 **Transform data → Manage parameters** 中替换为本机绝对路径，然后刷新。不要提交 `.pbi/` cache 或本机路径。

## 显示格式

- 金额：BRL，卡片按空间使用 BRL / 千 / 百万显示。
- 比率：百分比。
- 评分：两位小数。
- 订单与客户：整数。
- Footer：`Olist Brazilian E-Commerce Public Dataset · delivered 销售口径 · 历史观察数据`。

## 验收结果

- 4 个指定页面存在，页面尺寸均为 1440×810。
- PBIR 共 76 个 visual，JSON 可解析。
- 六张 mart 与一张 `KPI Measures` 表可由 Desktop 解析。
- 页面 KPI 与 Analytics overview 对账。
- PBIX 已重新打开并显示已加载数据。
- 四张截图来自真实 Power BI Desktop 页面。
- Olist 页面未使用不受数据支持的广告、成本、利润或确认退款指标。
