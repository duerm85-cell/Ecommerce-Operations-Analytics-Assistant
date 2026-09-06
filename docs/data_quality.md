# 数据质量与指标一致性

本项目将数据质量检查作为 pipeline 的最后一道门禁。检查覆盖输入合同、明细关系、业务等式、指标结果和 Power BI 工程结构，主要测试位于 `tests/test_data_quality.py`、`tests/test_external_product_source.py` 和 `tests/test_powerbi_project.py`。

## 质量检查范围

### 1. 空值检查

目标：确保关键业务字段可以参与关联、聚合和指标计算。

检查内容：

- 商品：`product_id`、`product_name`、`category`、`price`；
- 用户：`user_id`、`region`；
- 订单：`order_id`、`user_id`、`product_id`、`order_date`、`status`；
- 广告：`date`、`campaign_id`、`impressions`、`clicks`、`spend`；
- 外部商品 ODS：六个必需字段及数值转换结果。

关联测试：

- `DataQualityTests.test_required_fields_complete`
- `ExternalProductSourceTests.test_public_dataset_aliases_are_normalized`

### 2. 重复 ID 检查

目标：保证维度表和事实表的业务主键唯一，避免关联后产生重复统计。

检查内容：

- 商品 `product_id` 唯一；
- 用户 `user_id` 唯一；
- 订单 `order_id` 唯一；
- 广告的 `date + campaign_id` 组合唯一；
- 外部商品输入出现重复 ID 时拒绝或报告。

关联测试：`DataQualityTests.test_primary_keys_unique`。

### 3. 主外键一致性

目标：防止订单引用不存在的客户或商品，保证事实表能够正确连接维度表。

检查规则：

```text
orders.user_id ⊆ users.user_id
orders.product_id ⊆ products.product_id
```

关联测试：`DataQualityTests.test_foreign_keys`。

### 4. 类型、范围与业务等式

目标：识别数值越界、状态错误和金额关系破坏。

检查内容：

- 商品价格大于 0，评分在有效范围内；
- Hot Score 与 Opportunity Score 位于 0–100；
- 订单数量符合生成范围；
- 点击数不超过曝光数，转化数不超过点击数；
- `quantity × unit_price = gross_amount`；
- 完成订单满足净销售额等式；
- 退款和取消订单满足收入、退款额与成本规则；
- 日期、币种和订单状态符合数据合同。

关联测试：

- `DataQualityTests.test_ranges_and_equations`
- `DataQualityTests.test_date_currency_and_status_contract`
- `DataQualityTests.test_hot_score_formula`
- `DataQualityTests.test_opportunity_score_penalizes_competition`

### 5. 指标一致性

目标：确保同一业务指标在不同处理层不会因过滤条件或聚合方式不同而发生口径漂移。

默认 pipeline 会将 Python 计算结果与 SQLite SQL 结果对账，覆盖：

- GMV；
- 净销售额；
- 有效订单量；
- 毛利；
- CTR；
- CVR；
- ROAS。

`analysis/run_analysis.py` 使用严格容差比较结果；不一致时抛出异常。关联测试为 `DataQualityTests.test_sql_python_dashboard_kpis_match`。

### 6. Python、SQL、DAX 结果一致

一致性验证分为两个层次：

1. 每次 pipeline 自动执行 Python 与 SQLite SQL 对账，并核对 Dashboard KPI 输出。
2. Power BI 验证阶段在重新打开的 PBIX 中通过只读 DAX 查询核对 12 个核心 KPI，结果记录在 `reports/powerbi_validation.md`；自动化测试同时检查 TMDL 度量值、数据路径和页面结构仍然存在。

第二层不会在每次普通 pipeline 中启动 Power BI Desktop 或重新查询 DAX，因此文档不会把结构测试错误描述成实时 DAX 执行。当前 V1.2 已保存的 DAX 对账结果与 Python/SQL 基线一致。

关联测试与记录：

- `DataQualityTests.test_sql_python_dashboard_kpis_match`
- `PowerBIProjectTests.test_tmdl_model_is_portable_preserves_base_measures_and_fixes_rfm_blank`
- `reports/powerbi_validation.md`
- `reports/powerbi_design_v1.2.md`

## 测试与质量门禁映射

| 质量维度 | 自动化检查 | 失败影响 |
|---|---|---|
| 数据规模 | 最小商品、用户、订单规模 | pipeline 失败 |
| 空值 | 关键字段缺失数量 | pipeline 失败 |
| 主键 | 单列或组合键重复 | pipeline 失败 |
| 外键 | 订单与用户/商品集合关系 | pipeline 失败 |
| 业务规则 | 金额、状态、点击/转化关系 | pipeline 失败 |
| 可复现性 | 两个临时目录文件哈希比较 | pipeline 失败 |
| 指标口径 | Python/SQLite/Dashboard 对账 | pipeline 失败 |
| 外部商品 | 字段映射、回退、下游兼容 | pipeline 失败 |
| Power BI | PBIX/PBIP、页面、度量、截图结构 | pipeline 失败 |

## 运行方式

完整质量检查随 pipeline 自动运行：

```powershell
python run_pipeline.py
```

也可以单独运行测试：

```powershell
python -m unittest discover -s tests -v
```

只验证外部商品数据入口：

```powershell
python -m unittest tests.test_external_product_source -v
```

## 当前边界

- MySQL 文件具有结构与兼容性检查，但默认 pipeline 使用 SQLite 执行数据对账，不会自动连接外部 MySQL 服务。
- DAX 数值核对需要打开 Power BI 模型，普通单元测试只执行结构和已记录基线检查。
- 外部商品真实性不能替代真实订单、用户或广告数据；内部经营结论仍受模拟规则约束。
- 数据质量通过表示数据符合当前合同，不等于证明业务因果关系或真实市场代表性。

指标定义见 [business_metrics.md](business_metrics.md)，数据分层见 [data_architecture.md](data_architecture.md)，ETL 顺序见 [etl_pipeline.md](etl_pipeline.md)。
