[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$reportRoot = Join-Path $projectRoot 'Ecommerce-Operations-Analytics-Assistant.Report'
$modelRoot = Join-Path $projectRoot 'Ecommerce-Operations-Analytics-Assistant.SemanticModel'
$pagesRoot = Join-Path $reportRoot 'definition\pages'
$measureTable = 'KPI Measures'
$visualSchema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json'
$pageSchema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json'

if (-not (Test-Path -LiteralPath (Join-Path $reportRoot 'definition.pbir'))) {
    throw "Power BI report project was not found: $reportRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $modelRoot 'definition.pbism'))) {
    throw "Power BI semantic model project was not found: $modelRoot"
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    $directory = Split-Path -Parent $Path
    [void][System.IO.Directory]::CreateDirectory($directory)
    $json = $Value | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

function Get-StableId {
    param([Parameter(Mandatory = $true)][string]$Text)
    $sha = [System.Security.Cryptography.SHA1]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant().Substring(0, 20)
    }
    finally {
        $sha.Dispose()
    }
}

function New-Literal {
    param([Parameter(Mandatory = $true)][string]$Value)
    return [ordered]@{ expr = [ordered]@{ Literal = [ordered]@{ Value = $Value } } }
}

function New-SolidColor {
    param([Parameter(Mandatory = $true)][string]$Color)
    return [ordered]@{ solid = [ordered]@{ color = (New-Literal "'$Color'") } }
}

function New-Position {
    param([int]$X, [int]$Y, [int]$Width, [int]$Height, [int]$Z)
    return [ordered]@{ x = $X; y = $Y; z = $Z; height = $Height; width = $Width; tabOrder = $Z }
}

function New-MeasureProjection {
    param([string]$Measure)
    return [ordered]@{
        field = [ordered]@{
            Measure = [ordered]@{
                Expression = [ordered]@{ SourceRef = [ordered]@{ Entity = $measureTable } }
                Property = $Measure
            }
        }
        queryRef = "$measureTable.$Measure"
        nativeQueryRef = $Measure
    }
}

function New-ColumnProjection {
    param([string]$Table, [string]$Column, [switch]$Active)
    $projection = [ordered]@{
        field = [ordered]@{
            Column = [ordered]@{
                Expression = [ordered]@{ SourceRef = [ordered]@{ Entity = $Table } }
                Property = $Column
            }
        }
        queryRef = "$Table.$Column"
        nativeQueryRef = $Column
    }
    if ($Active) { $projection.active = $true }
    return $projection
}

function New-ContainerObjects {
    param([string]$Title, [switch]$HideTitle)
    return [ordered]@{
        title = @([ordered]@{ properties = [ordered]@{
            show = (New-Literal $(if ($HideTitle) { 'false' } else { 'true' }))
            text = (New-Literal "'$Title'")
            fontSize = (New-Literal '14D')
            fontColor = (New-SolidColor '#242424')
        } })
        subTitle = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
        background = @([ordered]@{ properties = [ordered]@{
            show = (New-Literal 'true')
            color = (New-SolidColor '#FFFFFF')
            transparency = (New-Literal '0D')
        } })
        border = @([ordered]@{ properties = [ordered]@{
            show = (New-Literal 'true')
            color = (New-SolidColor '#DDE3EA')
            radius = (New-Literal '8D')
        } })
        padding = @([ordered]@{ properties = [ordered]@{
            top = (New-Literal '8D')
            bottom = (New-Literal '8D')
            left = (New-Literal '8D')
            right = (New-Literal '8D')
        } })
        visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
    }
}

function Write-Visual {
    param([string]$PageName, [string]$Key, $Visual)
    $id = Get-StableId "$PageName/$Key"
    $Visual.name = $id
    Write-JsonFile (Join-Path $pagesRoot "$PageName\visuals\$id\visual.json") $Visual
}

function New-Page {
    param([string]$Name, [string]$DisplayName)
    $page = [ordered]@{
        '$schema' = $pageSchema
        name = $Name
        displayName = $DisplayName
        displayOption = 'FitToPage'
        height = 810
        width = 1440
        objects = [ordered]@{
            background = @([ordered]@{ properties = [ordered]@{
                color = (New-SolidColor '#F5F7FA')
                transparency = (New-Literal '0D')
            } })
            outspace = @([ordered]@{ properties = [ordered]@{
                color = (New-SolidColor '#E8EDF3')
                transparency = (New-Literal '0D')
            } })
        }
    }
    Write-JsonFile (Join-Path $pagesRoot "$Name\page.json") $page
    [void][System.IO.Directory]::CreateDirectory((Join-Path $pagesRoot "$Name\visuals"))
}

function Add-Textbox {
    param(
        [string]$Page, [string]$Key, [string]$Text,
        [int]$X, [int]$Y, [int]$Width, [int]$Height,
        [string]$FontSize = '16px', [string]$Color = '#242424',
        [string]$Background = '#F5F7FA', [switch]$Bold, [int]$Z = 100
    )
    $textStyle = [ordered]@{ fontFamily = 'Segoe UI'; fontSize = $FontSize; color = $Color }
    if ($Bold) { $textStyle.fontWeight = 'bold' }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = 'textbox'
            objects = [ordered]@{
                general = @([ordered]@{ properties = [ordered]@{
                    paragraphs = @([ordered]@{
                        textRuns = @([ordered]@{ value = $Text; textStyle = $textStyle })
                        horizontalTextAlignment = 'left'
                    })
                } })
            }
            visualContainerObjects = [ordered]@{
                background = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    color = (New-SolidColor $Background)
                    transparency = (New-Literal '0D')
                } })
                border = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                padding = @([ordered]@{ properties = [ordered]@{
                    top = (New-Literal '6D'); bottom = (New-Literal '6D'); left = (New-Literal '8D'); right = (New-Literal '8D')
                } })
                visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
            }
        }
    }
    Write-Visual $Page $Key $visual
}

function Add-Card {
    param(
        [string]$Page, [string]$Key, [string[]]$Measures,
        [int]$X, [int]$Y, [int]$Width, [int]$Height, [int]$Z = 200
    )
    $projections = @($Measures | ForEach-Object { New-MeasureProjection $_ })
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = 'cardVisual'
            query = [ordered]@{ queryState = [ordered]@{ Data = [ordered]@{ projections = $projections } } }
            objects = [ordered]@{
                value = @([ordered]@{ properties = [ordered]@{
                    fontSize = (New-Literal '20D')
                    bold = (New-Literal 'true')
                    fontColor = (New-SolidColor '#0F6CBD')
                }; selector = [ordered]@{ id = 'default' } })
                label = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    fontSize = (New-Literal '10D')
                }; selector = [ordered]@{ id = 'default' } })
                outline = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') }; selector = [ordered]@{ id = 'default' } })
                layout = @([ordered]@{ properties = [ordered]@{
                    topOuterMargin = (New-Literal '0L'); bottomOuterMargin = (New-Literal '0L'); leftOuterMargin = (New-Literal '0L'); rightOuterMargin = (New-Literal '0L'); paddingUniform = (New-Literal '0L')
                }; selector = [ordered]@{ id = 'default' } })
            }
            visualContainerObjects = (New-ContainerObjects '' -HideTitle)
        }
    }
    Write-Visual $Page $Key $visual
}

function Add-Slicer {
    param(
        [string]$Page, [string]$Key, [string]$Table, [string]$Column, [string]$Label,
        [int]$X, [int]$Y, [int]$Width, [int]$Height = 72,
        [ValidateSet('Dropdown', 'Between', 'Single')][string]$Mode = 'Dropdown',
        [string]$SyncGroup, [int]$Z = 300
    )
    $visualBody = [ordered]@{
        visualType = 'slicer'
        query = [ordered]@{ queryState = [ordered]@{ Values = [ordered]@{ projections = @((New-ColumnProjection $Table $Column)) } } }
        objects = [ordered]@{
            data = @([ordered]@{ properties = [ordered]@{ mode = (New-Literal "'$Mode'") } })
            header = @([ordered]@{ properties = [ordered]@{
                show = (New-Literal 'true')
                text = (New-Literal "'$Label'")
            } })
        }
        visualContainerObjects = [ordered]@{
            background = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'true'); color = (New-SolidColor '#FFFFFF'); transparency = (New-Literal '0D') } })
            border = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'true'); color = (New-SolidColor '#DDE3EA'); radius = (New-Literal '8D') } })
            padding = @([ordered]@{ properties = [ordered]@{ top = (New-Literal '6D'); bottom = (New-Literal '6D'); left = (New-Literal '8D'); right = (New-Literal '8D') } })
            visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
        }
    }
    if ($SyncGroup) { $visualBody.syncGroup = [ordered]@{ groupName = $SyncGroup; fieldChanges = $true; filterChanges = $true } }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = $visualBody
    }
    Write-Visual $Page $Key $visual
}

function Add-Chart {
    param(
        [string]$Page, [string]$Key,
        [ValidateSet('barChart', 'clusteredBarChart', 'clusteredColumnChart', 'columnChart', 'lineChart')][string]$Type,
        [string]$CategoryTable, [string]$CategoryColumn, [string[]]$Measures, [string]$Title,
        [int]$X, [int]$Y, [int]$Width, [int]$Height,
        [ValidateSet('MeasureDescending', 'CategoryAscending')][string]$Sort = 'MeasureDescending', [int]$Z = 400
    )
    $categoryProjection = New-ColumnProjection $CategoryTable $CategoryColumn -Active
    $measureProjections = @($Measures | ForEach-Object { New-MeasureProjection $_ })
    if ($Sort -eq 'CategoryAscending') {
        $sortField = $categoryProjection.field
        $direction = 'Ascending'
    }
    else {
        $sortField = $measureProjections[0].field
        $direction = 'Descending'
    }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = $Type
            query = [ordered]@{
                queryState = [ordered]@{
                    Category = [ordered]@{ projections = @($categoryProjection) }
                    Y = [ordered]@{ projections = $measureProjections }
                }
                sortDefinition = [ordered]@{
                    sort = @([ordered]@{ field = $sortField; direction = $direction })
                    isDefaultSort = $true
                }
            }
            objects = [ordered]@{
                categoryAxis = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'true'); fontSize = (New-Literal '10D') } })
                valueAxis = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'true'); gridlineStyle = (New-Literal "'dotted'") } })
                labels = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
            }
            visualContainerObjects = (New-ContainerObjects $Title)
        }
    }
    Write-Visual $Page $Key $visual
}

function Add-PageHeader {
    param([string]$Page, [string]$Title, [string]$Insight)
    Add-Textbox $Page 'page-title' $Title 24 16 760 52 '28px' '#17324D' '#F5F7FA' -Bold -Z 10
    Add-Textbox $Page 'simulation-banner' '⚠ 模拟数据 · TWD · 统计期 2025-01-01 至 2025-12-31' 860 18 550 44 '14px' '#7A4E00' '#FFF4CE' -Bold -Z 20
    Add-Textbox $Page 'page-insight' $Insight 24 776 1386 26 '12px' '#435466' '#E8F1FB' -Z 900
}

$additionalMeasures = @'

	/// Average normalized product heat score in the current filter context.
	measure 'Average Hot Score' = AVERAGE(products[hot_score])
		formatString: 0.00
		lineageTag: d997016a-cf51-48dc-8166-6a8a3c991751

	/// Average opportunity score; higher values indicate stronger demand with lower competition and price crowding.
	measure 'Average Opportunity Score' = AVERAGE(products[opportunity_score])
		formatString: 0.00
		lineageTag: a55dfd4c-59ca-46ae-bbc0-9479e135ec34

	/// Net sales returned only for the ten highest-selling products in the current selection.
	measure 'Top 10 Product Net Sales' =
			VAR ProductRank = RANKX(ALLSELECTED(products[product_name]), [Net Sales],, DESC, DENSE)
			RETURN IF(ProductRank <= 10, [Net Sales])
		formatString: #,0 "TWD"
		lineageTag: 2ab682e0-f679-4bd6-88ce-f4650fb2984d

	/// Gross profit for the same ten products ranked by net sales.
	measure 'Top 10 Product Gross Profit' =
			VAR ProductRank = RANKX(ALLSELECTED(products[product_name]), [Net Sales],, DESC, DENSE)
			RETURN IF(ProductRank <= 10, [Gross Profit])
		formatString: #,0 "TWD"
		lineageTag: f65443c7-38d0-487c-865c-6068e33decb0

	/// Opportunity score returned only for the ten highest-opportunity products in the current selection.
	measure 'Top 10 Opportunity Score' =
			VAR OpportunityRank = RANKX(ALLSELECTED(products[product_name]), [Average Opportunity Score],, DESC, DENSE)
			RETURN IF(OpportunityRank <= 10, [Average Opportunity Score])
		formatString: 0.00
		lineageTag: 53a51d42-a2e8-45bf-806e-ff310709f27e

	/// Hot score for the same ten products ranked by opportunity score.
	measure 'Hot Score for Opportunity Top 10' =
			VAR OpportunityRank = RANKX(ALLSELECTED(products[product_name]), [Average Opportunity Score],, DESC, DENSE)
			RETURN IF(OpportunityRank <= 10, [Average Hot Score])
		formatString: 0.00
		lineageTag: 48f52650-028f-498a-ae7b-44a6bc0398cc
'@

$measurePath = Join-Path $modelRoot 'definition\tables\KPI Measures.tmdl'
$measureText = [System.IO.File]::ReadAllText($measurePath)
if (-not $measureText.Contains("measure 'Average Hot Score'")) {
    $marker = "`tcolumn Dummy"
    $markerIndex = $measureText.IndexOf($marker, [StringComparison]::Ordinal)
    if ($markerIndex -lt 0) { throw 'Could not locate the calculated-table Dummy column in KPI Measures.tmdl.' }
    $measureText = $measureText.Insert($markerIndex, $additionalMeasures + [Environment]::NewLine)
    [System.IO.File]::WriteAllText($measurePath, $measureText, [System.Text.UTF8Encoding]::new($false))
}

# Power BI interprets an unescaped "NT$" custom format as date/time tokens in
# some desktop locales. Quote the ISO currency code so every machine renders it
# literally and consistently.
Get-ChildItem -LiteralPath (Join-Path $modelRoot 'definition\tables') -Filter '*.tmdl' | ForEach-Object {
    $tmdl = [System.IO.File]::ReadAllText($_.FullName)
    $normalized = $tmdl.Replace('NT$ #,0.00', '#,0.00 "TWD"').Replace('NT$ #,0', '#,0 "TWD"')
    if ($normalized -ne $tmdl) {
        [System.IO.File]::WriteAllText($_.FullName, $normalized, [System.Text.UTF8Encoding]::new($false))
    }
}

# PBIP source control must not retain the author machine's absolute path. Use a
# standard Power Query parameter so a reviewer can set one folder once and
# refresh all five imports. The distributable PBIX keeps its validated embedded
# data; this placeholder affects only refreshes of a clean PBIP checkout.
$dataRootExpression = @'
expression DataRoot = "C:\path\to\Ecommerce-Operations-Analytics-Assistant\dashboard\powerbi_data" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
	lineageTag: 31da920a-496c-46e2-8d20-f365f8bd9184
	annotation PBI_NavigationStepName = Navigation
	annotation PBI_ResultType = Text
'@
$expressionPath = Join-Path $modelRoot 'definition\expressions.tmdl'
[System.IO.File]::WriteAllText(
    $expressionPath,
    $dataRootExpression + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Get-ChildItem -LiteralPath (Join-Path $modelRoot 'definition\tables') -Filter '*.tmdl' | ForEach-Object {
    $tmdl = [System.IO.File]::ReadAllText($_.FullName)
    $portable = [regex]::Replace(
        $tmdl,
        'File\.Contents\("[A-Za-z]:\\[^"\r\n]*\\powerbi_data\\(?<file>products|users|orders|ads|calendar)\.csv"\)',
        'File.Contents(DataRoot & "\${file}.csv")'
    )
    if ($portable -ne $tmdl) {
        [System.IO.File]::WriteAllText($_.FullName, $portable, [System.Text.UTF8Encoding]::new($false))
    }
}

$modelPath = Join-Path $modelRoot 'definition\model.tmdl'
$modelText = [System.IO.File]::ReadAllText($modelPath)
if (-not $modelText.Contains('ref expression DataRoot')) {
    $modelText = $modelText.Replace(
        'ref cultureInfo zh-CN',
        "ref expression DataRoot$([Environment]::NewLine)$([Environment]::NewLine)ref cultureInfo zh-CN"
    )
    [System.IO.File]::WriteAllText($modelPath, $modelText, [System.Text.UTF8Encoding]::new($false))
}

# Power BI's serializer can leave more than one newline at EOF. Normalize all
# TMDL files so Git reviews stay clean without changing model semantics.
Get-ChildItem -LiteralPath (Join-Path $modelRoot 'definition') -Filter '*.tmdl' -File -Recurse | ForEach-Object {
    $tmdl = [System.IO.File]::ReadAllText($_.FullName)
    $normalized = $tmdl.TrimEnd("`r", "`n") + [Environment]::NewLine
    if ($normalized -ne $tmdl) {
        [System.IO.File]::WriteAllText($_.FullName, $normalized, [System.Text.UTF8Encoding]::new($false))
    }
}

$overview = '1e3893871908d0a9f051'
$products = '3a1b5d7e9f1029384756'
$users = '4b2c6e8f0a1928374655'
$ads = '5c3d7f9a1b2837465019'

New-Page $overview '经营总览'
Add-PageHeader $overview '经营总览 | Executive Overview' '洞察：促销与周末形成销售峰值；请联动毛利率与复购率判断增长质量。'
Add-Slicer $overview 'date' 'calendar' 'date' '日期范围' 24 74 330 74 -Mode Between -SyncGroup 'DateSync'
Add-Slicer $overview 'category' 'products' 'category' '类目' 370 74 250 74
Add-Slicer $overview 'region' 'users' 'region' '地区' 636 74 250 74
Add-Slicer $overview 'channel' 'users' 'acquisition_channel' '获客渠道' 902 74 250 74
Add-Textbox $overview 'scope-note' '有效成交口径：completed；GMV 另含 refunded 的成交额。' 1168 76 242 68 '11px' '#435466' '#FFFFFF' -Z 320
Add-Card $overview 'kpi-sales' @('GMV', 'Net Sales', 'Completed Orders', 'Gross Profit') 24 160 684 112
Add-Card $overview 'kpi-quality' @('Gross Margin %', 'AOV', 'Purchasing Users', 'Repeat Rate FY2025 %') 724 160 686 112
Add-Chart $overview 'monthly-trend' 'lineChart' 'calendar' 'month' @('Net Sales', 'GMV') '十二个月销售趋势（TWD）' 24 288 860 472 -Sort CategoryAscending
Add-Chart $overview 'category-contribution' 'clusteredBarChart' 'products' 'category' @('Net Sales', 'Gross Profit') '类目净销售额与毛利贡献（TWD）' 900 288 510 472

New-Page $products '商品分析'
Add-PageHeader $products '商品分析 | Product Intelligence' '洞察：Top 商品贡献应与毛利并看；高 Opportunity Score 表示需求更强、竞争与价格拥挤度更低。'
Add-Slicer $products 'category' 'products' 'category' '类目' 1090 74 320 74
Add-Card $products 'product-kpis' @('Product Count', 'High Opportunity Products', 'Units Sold', 'Net Sales', 'Gross Profit') 24 112 1050 112
Add-Textbox $products 'score-note' 'Hot Score：销量/评分/评论；Opportunity Score：需求↑、竞争↓、价格拥挤↓。' 1090 164 320 60 '11px' '#435466' '#FFFFFF' -Z 310
Add-Chart $products 'top-products' 'clusteredBarChart' 'products' 'product_name' @('Top 10 Product Net Sales', 'Top 10 Product Gross Profit') 'Top 10 商品：净销售额与毛利（TWD）' 24 240 446 520
Add-Chart $products 'price-band' 'clusteredColumnChart' 'products' 'price_band' @('Net Sales', 'Gross Profit') '价格带销售额与毛利（TWD）' 486 240 446 520 -Sort CategoryAscending
Add-Chart $products 'opportunity-products' 'clusteredBarChart' 'products' 'product_name' @('Top 10 Opportunity Score', 'Hot Score for Opportunity Top 10') '机会商品 Top 10：机会分与热度分' 948 240 462 520

New-Page $users '用户分析'
Add-PageHeader $users '用户分析 | Customer & RFM' '洞察：复购率按 2025 年至少 2 笔 completed 订单的购买用户计算；RFM 观察日为 2026-01-01。'
Add-Slicer $users 'region' 'users' 'region' '地区' 24 74 300 74
Add-Slicer $users 'segment' 'users' 'rfm_segment' 'RFM 客群' 340 74 330 74
Add-Slicer $users 'customer-type' 'users' 'customer_type' '新老用户' 686 74 300 74
Add-Card $users 'rfm-kpis' @('Purchasing Users', 'Repeat Rate FY2025 %', 'Average Recency', 'Average Frequency', 'Average Monetary') 24 160 980 112
Add-Card $users 'new-repeat' @('New Customers', 'Repeat Customers') 1020 160 390 112
Add-Chart $users 'rfm-segments' 'clusteredBarChart' 'users' 'rfm_segment' @('Registered Users') 'RFM 客群规模' 24 288 440 472
Add-Chart $users 'region-distribution' 'clusteredColumnChart' 'users' 'region' @('Registered Users') '用户地区分布' 480 288 440 472
Add-Chart $users 'rfm-profile' 'clusteredColumnChart' 'users' 'rfm_segment' @('Average Recency', 'Average Frequency') 'RFM 客群画像：Recency / Frequency' 936 288 474 472

New-Page $ads '广告分析'
Add-PageHeader $ads '广告分析 | Marketing Performance' '洞察：Attributed Revenue 仅为广告归因口径，不等于订单净销售额；优先暂停高 CPA、低 ROAS 活动并做增量测试。'
Add-Slicer $ads 'date' 'calendar' 'date' '日期范围' 24 74 350 74 -Mode Between -SyncGroup 'DateSync'
Add-Slicer $ads 'channel' 'ads' 'channel' '广告渠道' 390 74 300 74
Add-Slicer $ads 'campaign' 'ads' 'campaign_name' '广告活动' 706 74 400 74
Add-Textbox $ads 'attribution-note' '归因收入 ≠ 订单收入；金额均为 TWD。' 1122 78 288 64 '11px' '#435466' '#FFFFFF' -Z 320
Add-Card $ads 'volume-kpis' @('Ad Spend', 'Impressions', 'Clicks', 'Conversions', 'Attributed Revenue') 24 160 1386 108
Add-Card $ads 'efficiency-kpis' @('CTR %', 'CVR %', 'CPC', 'CPA', 'ROAS') 24 284 1386 108
Add-Chart $ads 'ad-trend' 'lineChart' 'calendar' 'month' @('Ad Spend', 'Attributed Revenue') '月度广告投入与归因收入（TWD）' 24 408 450 352 -Sort CategoryAscending
Add-Chart $ads 'campaign-compare' 'clusteredBarChart' 'ads' 'campaign_name' @('Ad Spend', 'Attributed Revenue') '活动投入与归因收入（TWD）' 490 408 450 352
Add-Chart $ads 'channel-roas' 'clusteredColumnChart' 'ads' 'channel' @('ROAS', 'CTR %', 'CVR %') '渠道效率：ROAS / CTR / CVR' 956 408 454 352

$pagesMetadata = [ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json'
    pageOrder = @($overview, $products, $users, $ads)
    activePageName = $overview
}
Write-JsonFile (Join-Path $pagesRoot 'pages.json') $pagesMetadata

Write-Host 'PBIR report generated: 4 pages.'
Write-Host 'Pages: 经营总览, 商品分析, 用户分析, 广告分析.'
