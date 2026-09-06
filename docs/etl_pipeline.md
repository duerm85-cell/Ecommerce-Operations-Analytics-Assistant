# ETL Pipeline 说明

本项目通过 `run_pipeline.py` 串联数据生成、分析、应用资产构建和自动化测试，形成可复现的轻量 ETL 流程。外部商品数据可以进入 ODS；用户、订单和广告仍由固定种子与业务规则生成。

## ETL 总览

```text
Extract
  ├─ 公开商品数据采集
  └─ 模拟业务数据生成
          ↓
Transform
  ├─ 数据清洗
  ├─ 类型转换
  ├─ 数据标准化
  └─ 指标与主题汇总计算
          ↓
Load
  ├─ CSV / SQLite
  ├─ MySQL 8 可选加载
  └─ Power BI / HTML Dashboard 输入
```

## Extract

### 商品数据采集

`crawler/product_crawler.py` 从本地公开数据集或无需认证的公共 CSV/ZIP URL 提取商品数据。采集层只接收以下标准字段：

- `product_id`
- `product_name`
- `category`
- `price`
- `rating`
- `review_count`

采集结果写入 `crawler/raw_data/raw_products.csv`，作为商品 ODS。URL 模式要求人工确认数据源条款，并遵守 `robots.txt` 与文件大小限制。

### 模拟业务数据生成

`data/generate_data.py` 使用固定种子生成：

- 用户数据；
- 订单数据；
- 广告数据；
- 日期维度；
- 外部商品数据不可用时的商品回退数据。

固定种子确保同一版本、同一输入和同一参数能够重复得到稳定结果。

## Transform

### 数据清洗

- 去除商品文本字段首尾空格；
- 拒绝空商品标识、名称和品类；
- 拒绝重复商品 ID；
- 过滤采集阶段的非法公开商品记录；
- 对外部商品品类执行显式业务映射，无法映射时停止处理。

### 类型转换

- 将价格与评分转换为数值类型；
- 将评价数转换为非负整数；
- 将订单、注册、广告和日历字段解析为日期；
- 将外部商品价格在进入分析层前统一为 TWD。

### 数据标准化

- 统一表名、字段名和 CSV 编码；
- 统一商品业务品类；
- 统一订单状态、币种和日期范围；
- 统一 Power BI、Python 与 SQL 使用的数据合同。

### 指标计算

`analysis/run_analysis.py` 基于 DWD 明细计算：

- GMV、净销售额、订单量、毛利、毛利率和 AOV；
- 购买用户数、复购率和 RFM 客群；
- CTR、CVR、CPC、CPA 和 ROAS；
- 月度、商品、品类、客户和广告主题汇总。

业务口径以 [business_metrics.md](business_metrics.md) 和 [metric_dictionary.md](metric_dictionary.md) 为准。

## Load

### CSV 明细与应用文件

`data/generate_data.py` 将标准化明细写入：

- `data/processed/*.csv`：DWD 明细数据；
- `data/sample/*_sample.csv`：可提交的小规模样例；
- `dashboard/powerbi_data/*.csv`：Power BI 刷新输入。

`analysis/run_analysis.py` 将主题汇总与指标结果写入 `reports/`，形成 DWS/ADS 输出。

### SQLite

`analysis/run_analysis.py` 使用 pandas 将五张明细表加载到 `data/analytics.sqlite`，建立主键与查询索引，并运行 SQL/Python 指标对账。SQLite 是默认 pipeline 中可直接执行的本地验证数据库。

### MySQL

`database/` 提供 MySQL 8 的表结构、索引、导入适配和业务分析 SQL。MySQL 加载属于可选部署路径，不在默认 `run_pipeline.py` 中自动连接，避免依赖本机凭据或修改外部数据库。

### Power BI

Power BI 从 `dashboard/powerbi_data` 读取标准化输入，并通过 TMDL/DAX 语义层提供业务指标和决策页面。本阶段没有修改 Power BI 文件或 DAX 逻辑。

## `run_pipeline.py` 执行顺序

`run_pipeline.py` 按固定顺序执行四个阶段：

1. `data/generate_data.py`：提取可用商品输入，生成内部模拟数据，完成明细标准化与加载。
2. `analysis/run_analysis.py`：构建 SQLite、计算指标、生成主题汇总并执行 SQL/Python 对账。
3. `dashboard/build_dashboard.py`：根据 ADS 输出生成浏览器 Dashboard。
4. `python -m unittest discover -s tests -v`：执行数据质量和 Power BI 结构验证。

每个阶段通过子进程顺序执行并启用失败即停止。任何阶段返回非零状态时，pipeline 不会继续宣称成功。

## 外部商品数据的安全验证方式

为了避免直接覆盖当前 Power BI 输入，首次验证外部商品数据时应将三个输出目录指向临时位置：

```powershell
python data/generate_data.py `
  --raw-products crawler/raw_data/raw_products.csv `
  --output C:\temp\ecommerce-etl\processed `
  --samples C:\temp\ecommerce-etl\sample `
  --powerbi C:\temp\ecommerce-etl\powerbi
```

确认商品覆盖率、币种、品类映射、订单适配和 KPI 影响后，再决定是否刷新正式应用层数据。

## 可复现与失败策略

- 外部商品文件缺失或只有表头：使用原商品生成逻辑。
- 外部商品文件存在但结构或数据非法：明确失败，不静默回退。
- 用户、订单和广告：固定种子生成逻辑保持不变。
- SQL/Python 核心指标不一致：抛出错误并终止。
- 任一自动化测试失败：pipeline 返回失败状态。

完整分层架构见 [data_architecture.md](data_architecture.md)，质量门禁见 [data_quality.md](data_quality.md)。
