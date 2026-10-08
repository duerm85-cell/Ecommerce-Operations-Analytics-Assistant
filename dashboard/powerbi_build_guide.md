# Power BI 构建与刷新指南

## Olist V2（主版本）

### 直接打开 PBIX

打开 `dashboard/powerbi_project/Ecommerce-Operations-Analytics-Olist-V2.pbix`。该文件已经在 Power BI Desktop 2.157.879.0 中完成真实数据刷新，并经过关闭/重新打开验证。

四个页面为：经营总览、商品与品类分析、客户价值、评价与订单体验。

### 从 PBIP 刷新

1. 运行 Olist Analytics 构建，生成 `dashboard/powerbi_data/olist_*.csv`。
2. 打开 `powerbi_project/Ecommerce-Operations-Analytics-Olist-V2.pbip`。
3. 进入 **Transform data → Manage parameters**。
4. 将 `DataRoot` 设置为本机仓库下 `dashboard/powerbi_data` 的绝对路径。
5. Apply 并 Refresh，核对总览指标后保存。
6. 不要提交 `.pbi/`、recovery、本机 settings 或实际绝对路径。

PBIP 的提交版本使用中性示例路径。六个 partition 都通过 `DataRoot` 加 CSV 文件名读取数据。

### 生成脚本

- `powerbi_project/generate_olist_semantic_model.ps1`：生成 Olist PBIP/TMDL 语义模型。
- `powerbi_project/generate_olist_pbir_report.ps1`：生成四页 PBIR，并复用 Legacy 已验证的视觉结构。

这些脚本用于可重复维护；普通查看者只需打开 PBIX。

### Olist 指标边界

- 销售与客户指标使用原始 `order_status = 'delivered'`。
- Merchandise GMV 来自 item `price_brl`，不含运费。
- Paid Value 来自 payment fact，不能重命名为 Merchandise GMV。
- 客户统一身份使用 `customer_unique_id`。
- Olist 不提供可靠的广告、商品成本、利润或确认退款数据，因此报表不包含相关 KPI。

## Legacy Synthetic V1.1/V1.2

Legacy PBIX、PBIP、PBIR、TMDL、主题、截图与 HTML 预览仍原样保留，用于历史对照和回归验证。Synthetic 的 GMV、Net Sales、Gross Profit、广告花费、CTR、CPA、ROAS 和 TWD 口径仅属于 Legacy，不能用于解释 Olist 主版本。

Legacy PBIP 若需刷新，仍按原流程生成 Synthetic CSV，并将其 `DataRoot` 指向 `dashboard/powerbi_data`。Olist 与 Synthetic 的项目目录、模型和 PBIX 相互独立。
