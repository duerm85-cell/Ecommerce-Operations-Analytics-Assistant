# 项目摘要

本项目把 Olist 的 9 个公开历史 CSV 构建为可验证的数据分析链路：源文件校验、ODS、DWD 维度/事实模型、客户身份桥、Analytics marts、CSV 导出和 Power BI 四页报表。

核心成果包括：

- 保留来源语义和技术 lineage 的 ODS；
- 四张维度、一张客户身份桥和四张独立事实表；
- 以 `customer_unique_id` 为统一身份的 RFM 与复购分析；
- 防止多事实 join 放大的 GMV / Paid Value 独立对账；
- 6 个稳定 Power BI mart 与可移植 `DataRoot`；
- 已刷新、保存并重开验证的 Olist PBIX；
- 对数据缺失、观察性结论和指标口径的明确限制。

Synthetic V1.1/V1.2 继续作为 Legacy 保存，但 Olist 是 README、数据层和 Power BI 的主叙事。
