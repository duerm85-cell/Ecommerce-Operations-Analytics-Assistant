# Olist 业务洞察

以下结果来自已验证的 Olist Analytics marts。销售指标使用 delivered 订单，客户身份使用 `customer_unique_id`，金额单位为 BRL。数据是历史观察数据，可能解释不等于因果结论。

## 1. 当前快照中的复购比例较低

**发现：** 只有 3.00% 的购买客户至少完成两笔 delivered 订单。

**证据：** 93,358 位购买客户中有 2,801 位复购客户；90,557 位客户仅有一笔 delivered 订单。

**解释边界：** 结果可能同时受市场购物习惯、可观察时间窗和数据集外身份缺失影响。

**可验证方向：** 按首购 cohort 和品类分析首单到第二单的转化，不把所有一次购买客户视为同一留存问题。

## 2. RFM 客户集中在 Hibernating 与 New Customers

**发现：** 两个分群合计占购买客户的 77.95%。

**证据：** Hibernating 为 36,650 人（39.26%），New Customers 为 36,118 人（38.69%）。

**解释边界：** 分群依赖确定性 RFM 阈值，只是描述性标签。

**可验证方向：** 对近期一次购买客户和较早流失客户使用不同的观察窗口与衡量方式。

## 3. `health_beauty` 的商品成交额最高

**发现：** `health_beauty` 是 delivered Merchandise GMV 最高的品类。

**证据：** 该品类有 8,647 个 delivered 订单、9,465 个 item records、BRL 1,233,131.72 Merchandise GMV，占总额 9.33%；平均评分 4.23，低评分占比 11.43%。

**解释边界：** 当前 mart 不能判断贡献是否集中于少数商品或卖家。

**可验证方向：** 进一步检查该品类的商品、卖家集中度与缺货情况。

## 4. `office_furniture` 同时出现评分和运费风险信号

**发现：** 在至少 1,000 个 delivered 订单的品类中，`office_furniture` 低评分占比最高。

**证据：** 1,254 个订单、BRL 268,154.31 Merchandise GMV、平均评分 3.64、低评分占比 22.02%、运费占比 25.01%。

**解释边界：** 评价记录在订单粒度；低评分与较高运费同时出现，不能证明运费或配送导致评分。

**可验证方向：** 按卖家、商品尺寸、配送距离、损坏和实际交付时长继续调查。

## 5. 成熟品类间的运费负担差异明显

**发现：** 在至少 500 个 delivered 订单的品类中，`electronics` 运费占比最高。

**证据：** 2,517 个订单的运费占 Merchandise GMV 29.46%；`office_furniture` 为 25.01%，`furniture_decor` 为 23.65%。

**解释边界：** 品类 mart 不能单独识别商品价格、尺寸、卖家位置或距离中的具体原因。

## 6. 2017-11 的 delivered GMV 最高

**证据：** 2017-11 有 7,289 个 delivered 订单、BRL 987,765.37 Merchandise GMV、BRL 1,153,528.05 Paid Value，平均评分 3.99。

**解释边界：** 数据集没有广告流量或 campaign 数据，不能把峰值归因于促销。

**可验证方向：** 与相邻月份比较品类结构、商品价格、卖家参与和客户 cohort。

## 7. Merchandise GMV 与 Paid Value 必须分开

**发现：** delivered Paid Value 比 Merchandise GMV 高 BRL 2,200,963.66。

**证据：** Merchandise GMV 为 BRL 13,221,498.11，Paid Value 为 BRL 15,422,461.77，freight value 为 BRL 2,198,275.64；Paid Value 比 GMV 加运费多 BRL 2,688.02。

**解释边界：** payment totals 与 item-price totals 是不同事实。运费解释了大部分差额，剩余差异需要在订单粒度核对支付行为。

## 时间边界

首尾月份不完整。2016-09 只有 4 个 placed orders；2018-09 和 2018-10 只有 16 和 4 个 placed orders，当前 delivered 销售口径中没有交付订单。若不显式处理 partial period，不应据此做环比结论。
