[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$dashboardRoot = Split-Path -Parent $projectRoot
$modelName = 'Ecommerce-Operations-Analytics-Olist-V2'
$reportRoot = Join-Path $projectRoot "$modelName.Report"
$modelRoot = Join-Path $projectRoot "$modelName.SemanticModel"
$pagesRoot = Join-Path $reportRoot 'definition\pages'
$measureTable = 'KPI Measures'
$visualSchema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json'
$pageSchema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json'
$themeSource = Join-Path $dashboardRoot 'powerbi_theme\executive_storytelling_v1.2.json'
$themeFileName = 'OlistExecutiveV2.json'
$themeTarget = Join-Path $reportRoot "StaticResources\RegisteredResources\$themeFileName"
$baseThemeSource = Join-Path $projectRoot 'Ecommerce-Operations-Analytics-Assistant.Report\StaticResources\SharedResources\BaseThemes\Fluent2-CY26SU08.json'
$baseThemeTarget = Join-Path $reportRoot 'StaticResources\SharedResources\BaseThemes\Fluent2-CY26SU08.json'

$colors = [ordered]@{
    Page = '#F6F8FB'
    Card = '#FFFFFF'
    Ink = '#16324F'
    Muted = '#526579'
    Blue = '#2F80ED'
    Teal = '#16A6A1'
    Amber = '#F2B84B'
    Red = '#E7685D'
    Border = '#DDE5EE'
    PaleBlue = '#EAF3FF'
    PaleTeal = '#E9F7F5'
    PaleAmber = '#FFF8E6'
    PaleRed = '#FDEEEE'
}

if (-not (Test-Path -LiteralPath (Join-Path $modelRoot 'definition.pbism'))) {
    throw "Run generate_olist_semantic_model.ps1 first: $modelRoot"
}
if (-not (Test-Path -LiteralPath $themeSource)) {
    throw "Power BI theme not found: $themeSource"
}

# Reuse the tested PBIR helper functions and visual styling from the Synthetic
# V1.2 generator without executing or changing the legacy report itself.
$legacyGenerator = Join-Path $projectRoot 'generate_pbir_report_v1_2.ps1'
$legacySource = [System.IO.File]::ReadAllText($legacyGenerator)
$helperStart = $legacySource.IndexOf('function Write-JsonFile', [StringComparison]::Ordinal)
$helperEnd = $legacySource.IndexOf('function Add-PageHeader', [StringComparison]::Ordinal)
if ($helperStart -lt 0 -or $helperEnd -le $helperStart) {
    throw 'Could not locate reusable PBIR helper functions in the V1.2 generator.'
}
Invoke-Expression $legacySource.Substring($helperStart, $helperEnd - $helperStart)

function Add-PageHeader {
    param([string]$Page, [string]$Title)
    Add-Textbox $Page 'page-title' $Title 24 8 452 52 '25px' $colors.Ink $colors.Page -Bold -Z 10
    Add-NavigationButton $Page 'nav-overview' '经营总览' 'olist_overview' 500 -Active:($Page -eq 'olist_overview')
    Add-NavigationButton $Page 'nav-category' '商品与品类' 'olist_category' 655 -Active:($Page -eq 'olist_category')
    Add-NavigationButton $Page 'nav-customer' '客户价值' 'olist_customer' 810 -Active:($Page -eq 'olist_customer')
    Add-NavigationButton $Page 'nav-experience' '评价与订单体验' 'olist_experience' 965 -Active:($Page -eq 'olist_experience')
    Add-Textbox $Page 'data-banner' 'Olist 公开历史数据 · BRL' 1140 14 276 44 '13px' $colors.Ink $colors.PaleAmber -Bold -Align center -Z 20
    Add-Textbox $Page 'footer' 'Olist Brazilian E-Commerce Public Dataset · delivered 销售口径 · 历史观察数据' 24 774 1392 30 '10px' $colors.Muted $colors.Page -Align center -Z 900
}

[void][System.IO.Directory]::CreateDirectory($pagesRoot)
[void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $themeTarget))
[void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $baseThemeTarget))
[System.IO.File]::Copy($themeSource, $themeTarget, $true)
[System.IO.File]::Copy($baseThemeSource, $baseThemeTarget, $true)

Write-JsonFile (Join-Path $reportRoot '.platform') ([ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json'
    metadata = [ordered]@{ type = 'Report'; displayName = $modelName }
    config = [ordered]@{ version = '2.0'; logicalId = '5148b418-65ca-41b5-9837-3f94f0e5a887' }
})
Write-JsonFile (Join-Path $reportRoot 'definition.pbir') ([ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json'
    version = '4.0'
    datasetReference = [ordered]@{ byPath = [ordered]@{ path = "../$modelName.SemanticModel" } }
})
Write-JsonFile (Join-Path $reportRoot 'definition\version.json') ([ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json'
    version = '2.0.0'
})

$reportDefinition = [ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json'
    themeCollection = [ordered]@{
        baseTheme = [ordered]@{
            name = 'Fluent2-CY26SU08'
            reportVersionAtImport = [ordered]@{ visual = '2.12.0'; report = '3.4.0'; page = '2.3.1' }
            type = 'SharedResources'
        }
        customTheme = [ordered]@{
            name = $themeFileName
            reportVersionAtImport = [ordered]@{ visual = '2.12.0'; report = '3.4.0'; page = '2.3.1' }
            type = 'RegisteredResources'
        }
    }
    objects = [ordered]@{
        section = @([ordered]@{ properties = [ordered]@{ verticalAlignment = (New-Literal "'Top'") } })
    }
    resourcePackages = @(
        [ordered]@{
            name = 'SharedResources'; type = 'SharedResources'
            items = @([ordered]@{ name = 'Fluent2-CY26SU08'; path = 'BaseThemes/Fluent2-CY26SU08.json'; type = 'BaseTheme' })
        },
        [ordered]@{
            name = 'RegisteredResources'; type = 'RegisteredResources'
            items = @([ordered]@{ name = $themeFileName; path = $themeFileName; type = 'CustomTheme' })
        }
    )
    settings = [ordered]@{
        useStylableVisualContainerHeader = $true
        hideVisualContainerHeader = $true
        exportDataMode = 'AllowSummarized'
        defaultDrillFilterOtherVisuals = $true
        allowChangeFilterTypes = $true
        useEnhancedTooltips = $true
        useDefaultAggregateDisplayName = $true
        isPersistentUserStateDisabled = $true
    }
}
Write-JsonFile (Join-Path $reportRoot 'definition\report.json') $reportDefinition

$overviewPage = 'olist_overview'
$categoryPage = 'olist_category'
$customerPage = 'olist_customer'
$experiencePage = 'olist_experience'

New-Page $overviewPage '经营总览'
Add-PageHeader $overviewPage '经营总览'
Add-Textbox $overviewPage 'scope-note' '口径：订单和销售指标使用原始 order_status = delivered；商品成交额不含运费，付款金额与商品成交额分开。' 24 70 1392 64 '12px' $colors.Muted $colors.Card -Z 300
Add-DynamicTextCard $overviewPage 'business-conclusion' 'Overview Insight Text' 24 146 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $overviewPage 'kpi-gmv' 'Merchandise GMV' '商品成交额' 24 216 218 84 $colors.Blue 1000000 2 -FontSize 22
Add-KpiCard $overviewPage 'kpi-orders' 'Orders' '订单数' 258 216 218 84 $colors.Blue 0 0 -FontSize 22
Add-KpiCard $overviewPage 'kpi-customers' 'Purchasing Customers' '购买客户数' 492 216 218 84 $colors.Blue 0 0 -FontSize 22
Add-KpiCard $overviewPage 'kpi-aov' 'AOV' '平均订单金额' 726 216 218 84 $colors.Teal 0 2 -FontSize 22
Add-KpiCard $overviewPage 'kpi-repeat' 'Repeat Purchase Rate' '复购率' 960 216 218 84 $colors.Teal 0 2 -FontSize 22
Add-KpiCard $overviewPage 'kpi-review' 'Average Review Score' '平均评分' 1194 216 222 84 $colors.Amber 0 2 -FontSize 22
Add-Chart $overviewPage 'monthly-gmv' 'lineChart' 'olist_monthly_performance' 'month_key' '月份' @(
    @{ Name = 'Monthly GMV'; Label = '商品成交额（BRL）'; Color = $colors.Blue }
) '月度商品成交额趋势' 24 316 680 260 -Sort CategoryAscending -CategoryMargin 18
Add-Chart $overviewPage 'monthly-orders' 'lineChart' 'olist_monthly_performance' 'month_key' '月份' @(
    @{ Name = 'Monthly Orders'; Label = 'delivered 订单数'; Color = $colors.Teal }
) '月度订单趋势' 720 316 696 260 -Sort CategoryAscending -CategoryMargin 18
Add-Chart $overviewPage 'top-categories' 'clusteredBarChart' 'olist_category_performance' 'category_display_name' '品类' @(
    @{ Name = 'Category GMV'; Label = '商品成交额（BRL）'; Color = $colors.Blue }
) '品类商品成交额（按成交额降序）' 24 590 680 168 -CategoryMargin 42
Add-Textbox $overviewPage 'overview-action' '阅读提示｜2016-09 与 2018-09/10 为不完整月份；趋势结论应结合订单量、品类结构和数据边界解释，不把观察结果写成因果结论。' 720 590 696 168 '13px' $colors.Ink $colors.PaleAmber -Bold -Z 500

New-Page $categoryPage '商品与品类分析'
Add-PageHeader $categoryPage '商品与品类分析'
Add-Slicer $categoryPage 'category' 'olist_category_performance' 'category_display_name' '品类' 24 70 420 76
Add-Textbox $categoryPage 'metric-note' '不使用成本、毛利、热度分或机会分。评价来自订单级 review，跨品类订单会按订单—品类关系归属。' 460 70 756 76 '11px' $colors.Muted $colors.Card -Z 310
Add-ClearSlicersButton $categoryPage
Add-DynamicTextCard $categoryPage 'business-conclusion' 'Category Insight Text' 24 158 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $categoryPage 'kpi-gmv' 'Category GMV' '品类商品成交额' 24 228 266 82 $colors.Blue 1000000 2
Add-KpiCard $categoryPage 'kpi-units' 'Units Sold' '销售件数' 306 228 266 82 $colors.Blue 0 0
Add-KpiCard $categoryPage 'kpi-price' 'Average Item Price' '平均商品价格' 588 228 264 82 $colors.Teal 0 2
Add-KpiCard $categoryPage 'kpi-freight' 'Category Freight Value' '运费金额' 868 228 266 82 $colors.Amber 1000000 2
Add-KpiCard $categoryPage 'kpi-freight-ratio' 'Category Freight Ratio' '运费占比' 1150 228 266 82 $colors.Red 0 2
Add-ScatterChart $categoryPage 'category-matrix' 'olist_category_performance' 'category_display_name' 'olist_category_performance' 'category_translation_status' 'Category GMV' 'Category Freight Ratio' 'Category Orders' @(
    @{ Name = 'Units Sold'; Label = '销售件数' },
    @{ Name = 'Category Average Review Score'; Label = '平均评分' },
    @{ Name = 'Category Low Rating Rate'; Label = '低评分占比' }
) '品类矩阵：商品成交额 × 运费占比（气泡=订单数）' '商品成交额（BRL）' '运费占比' 24 322 680 284
Add-Chart $categoryPage 'category-gmv' 'clusteredBarChart' 'olist_category_performance' 'category_display_name' '品类' @(
    @{ Name = 'Category GMV'; Label = '商品成交额（BRL）'; Color = $colors.Blue }
) '品类商品成交额' 720 322 696 284 -CategoryMargin 48
Add-Chart $categoryPage 'category-review' 'clusteredBarChart' 'olist_category_performance' 'category_display_name' '品类' @(
    @{ Name = 'Category Average Review Score'; Label = '平均评分'; Color = $colors.Teal }
) '品类平均评分' 24 622 680 136 -CategoryMargin 42
Add-Chart $categoryPage 'category-low-rating' 'clusteredBarChart' 'olist_category_performance' 'category_display_name' '品类' @(
    @{ Name = 'Category Low Rating Rate'; Label = '低评分占比'; Color = $colors.Red }
) '品类低评分占比' 720 622 696 136 -CategoryMargin 42

New-Page $customerPage '客户价值'
Add-PageHeader $customerPage '客户价值'
Add-Slicer $customerPage 'segment' 'olist_customer_rfm' 'rfm_segment' 'RFM 客户分群' 24 70 420 76
Add-Textbox $customerPage 'identity-note' '客户分析统一使用 customer_unique_id；RFM 观察日为 2018-08-30，分群为确定性描述规则，不是预测模型。' 460 70 756 76 '11px' $colors.Muted $colors.Card -Z 310
Add-ClearSlicersButton $customerPage
Add-DynamicTextCard $customerPage 'business-conclusion' 'Customer Insight Text' 24 158 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $customerPage 'kpi-customers' 'RFM Customers' '购买客户数' 24 228 266 82 $colors.Blue 0 0
Add-KpiCard $customerPage 'kpi-repeat-customers' 'RFM Repeat Customers' '复购客户数' 306 228 266 82 $colors.Teal 0 0
Add-KpiCard $customerPage 'kpi-repeat-rate' 'RFM Repeat Rate' '复购率' 588 228 264 82 $colors.Teal 0 2
Add-KpiCard $customerPage 'kpi-recency' 'Average Recency' '平均 Recency（天）' 868 228 266 82 $colors.Amber 0 1
Add-KpiCard $customerPage 'kpi-monetary' 'Average Monetary' '平均 Monetary' 1150 228 266 82 $colors.Blue 0 2
Add-Chart $customerPage 'segment-size' 'clusteredBarChart' 'olist_customer_rfm' 'rfm_segment' 'RFM 客户分群' @(
    @{ Name = 'RFM Customers'; Label = '客户数'; Color = $colors.Blue }
) 'RFM 客户分群人数' 24 322 680 284 -CategoryMargin 45
Add-Chart $customerPage 'segment-value' 'clusteredBarChart' 'olist_customer_rfm' 'rfm_segment' 'RFM 客户分群' @(
    @{ Name = 'Customer Monetary Value'; Label = 'Monetary Value（BRL）'; Color = $colors.Teal }
) 'RFM 客户分群 Monetary Value' 720 322 696 284 -CategoryMargin 45
Add-Chart $customerPage 'segment-recency' 'clusteredColumnChart' 'olist_customer_rfm' 'rfm_segment' 'RFM 客户分群' @(
    @{ Name = 'Average Recency'; Label = '平均 Recency（天）'; Color = $colors.Amber }
) '各分群平均 Recency' 24 622 680 136 -CategoryMargin 24
Add-Chart $customerPage 'segment-frequency' 'clusteredColumnChart' 'olist_customer_rfm' 'rfm_segment' 'RFM 客户分群' @(
    @{ Name = 'Average Frequency'; Label = '平均 Frequency'; Color = $colors.Blue }
) '各分群平均 Frequency' 720 622 696 136 -CategoryMargin 24

New-Page $experiencePage '评价与订单体验'
Add-PageHeader $experiencePage '评价与订单体验'
Add-Textbox $experiencePage 'scope-note' '现有 mart 未提供交付时长，因此本页只展示可复核的评分、低评分、取消率与运费指标，不声称分析配送时效。' 24 70 1392 64 '12px' $colors.Muted $colors.Card -Z 300
Add-DynamicTextCard $experiencePage 'business-conclusion' 'Experience Insight Text' 24 146 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $experiencePage 'kpi-review' 'Average Review Score' '平均评分' 24 216 336 84 $colors.Teal 0 2
Add-KpiCard $experiencePage 'kpi-canceled' 'Canceled Orders' '取消订单数' 376 216 336 84 $colors.Red 0 0
Add-KpiCard $experiencePage 'kpi-cancel-rate' 'Cancel Rate' '取消率' 728 216 336 84 $colors.Red 0 2
Add-KpiCard $experiencePage 'kpi-freight-ratio' 'Freight Ratio' '整体运费占比' 1080 216 336 84 $colors.Amber 0 2
Add-Chart $experiencePage 'monthly-review' 'lineChart' 'olist_monthly_performance' 'month_key' '月份' @(
    @{ Name = 'Monthly Average Review Score'; Label = '平均评分'; Color = $colors.Teal }
) '月度平均评分' 24 316 680 260 -Sort CategoryAscending -CategoryMargin 18
Add-Chart $experiencePage 'monthly-cancel' 'lineChart' 'olist_monthly_performance' 'month_key' '月份' @(
    @{ Name = 'Monthly Cancel Rate'; Label = '取消率'; Color = $colors.Red }
) '月度取消率' 720 316 696 260 -Sort CategoryAscending -CategoryMargin 18
Add-Chart $experiencePage 'category-low-rating' 'clusteredBarChart' 'olist_category_performance' 'category_display_name' '品类' @(
    @{ Name = 'Category Low Rating Rate'; Label = '低评分占比'; Color = $colors.Red }
) '品类低评分占比' 24 590 680 168 -CategoryMargin 42
Add-Chart $experiencePage 'category-freight-ratio' 'clusteredBarChart' 'olist_category_performance' 'category_display_name' '品类' @(
    @{ Name = 'Category Freight Ratio'; Label = '运费占比'; Color = $colors.Amber }
) '品类运费占比' 720 590 696 168 -CategoryMargin 42

Write-JsonFile (Join-Path $pagesRoot 'pages.json') ([ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json'
    pageOrder = @($overviewPage, $categoryPage, $customerPage, $experiencePage)
    activePageName = $overviewPage
})

Write-Host 'Olist PBIR report generated: 4 pages.'
Write-Host 'Pages: 经营总览, 商品与品类分析, 客户价值, 评价与订单体验.'
Write-Host 'Visual layout and navigation reuse the validated Synthetic V1.2 PBIR helper system.'
