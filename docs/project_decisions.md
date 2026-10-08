# 项目决策记录

## 为什么使用 Olist 作为主版本

Olist 提供订单、商品、支付、评价、客户、卖家和地理信息等不同粒度的公开历史数据，适合验证多事实表建模、客户身份桥接、指标对账和可复现分析。项目明确标注数据来源与历史边界，不把公开数据描述为企业内部生产数据。

## 为什么保留 Synthetic

Synthetic V1.1/V1.2 记录了早期固定种子数据、广告分析与 Power BI 视觉系统的演进。它继续保留用于历史对照和回归检查，但与 Olist 数据库、指标和报表隔离。

## 为什么不做宽表直连

订单商品、支付和评价都是一对多事实。直接 join 会放大金额和记录数。因此各事实先独立聚合到 `order_id`，再进入 overview 和 monthly marts；品类与客户金额只从 item fact 计算。

## 为什么需要 customer identity bridge

`customer_id` 对应订单级客户记录，`customer_unique_id` 才是跨订单稳定身份。所有购买客户、复购与 RFM 指标使用后者，bridge 保留两者的来源关系。

## 为什么 Olist 没有广告与利润页

数据集中没有可靠的广告曝光、点击、花费、归因收入和商品成本，因此不计算 CTR、CVR、CPA、ROAS、Gross Profit 或 Gross Margin。Legacy Synthetic 中的这些指标不会迁移到 Olist。
