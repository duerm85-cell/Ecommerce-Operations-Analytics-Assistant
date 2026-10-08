[CmdletBinding()]
param(
    [string]$BuildDataRoot = 'C:\path\to\Ecommerce-Operations-Analytics-Assistant\dashboard\powerbi_data'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$modelName = 'Ecommerce-Operations-Analytics-Olist-V2'
$modelRoot = Join-Path $projectRoot "$modelName.SemanticModel"
$reportRoot = Join-Path $projectRoot "$modelName.Report"
$definitionRoot = Join-Path $modelRoot 'definition'
$tablesRoot = Join-Path $definitionRoot 'tables'

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )
    [void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $Path))
    [System.IO.File]::WriteAllText(
        $Path,
        $Content.TrimEnd("`r", "`n") + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    Write-Utf8File -Path $Path -Content ($Value | ConvertTo-Json -Depth 20)
}

function Get-LineageTag {
    param([Parameter(Mandatory = $true)][string]$Key)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes("olist-v2/$Key"))
        $guidBytes = [byte[]]::new(16)
        [Array]::Copy($bytes, $guidBytes, 16)
        return ([guid]::new($guidBytes)).ToString()
    }
    finally {
        $sha.Dispose()
    }
}

function New-TmdlTable {
    param(
        [Parameter(Mandatory = $true)][string]$TableName,
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][array]$Columns,
        [Parameter(Mandatory = $true)][string]$Description,
        [string]$AdditionalPowerQuery = '',
        [string]$PowerQueryOutputStep = '#"Changed Type"'
    )

    $columnBlocks = foreach ($column in $Columns) {
        $lines = @(
            "`tcolumn $($column.Name)",
            "`t`tdataType: $($column.Type)",
            "`t`tlineageTag: $(Get-LineageTag "$TableName/$($column.Name)")"
        )
        if ($column.Hidden) { $lines += "`t`tisHidden" }
        if ($column.Format) { $lines += "`t`tformatString: $($column.Format)" }
        $lines += "`t`tsummarizeBy: $($column.Summarize)"
        $lines += "`t`tsourceColumn: $($column.Source)"
        $lines -join [Environment]::NewLine
    }

    $typePairs = $Columns | ForEach-Object {
        $mType = switch ($_.Type) {
            'int64' { 'Int64.Type' }
            'double' { 'type number' }
            'dateTime' { 'type date' }
            default { 'type text' }
        }
        '{"' + $_.Source + '", ' + $mType + '}'
    }
    $changedType = '#"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {' + ($typePairs -join ', ') + '}, "en-US")'
    $extra = if ($AdditionalPowerQuery) { ',' + [Environment]::NewLine + $AdditionalPowerQuery } else { '' }

    return @"
/// $Description
table $TableName
	lineageTag: $(Get-LineageTag $TableName)

$($columnBlocks -join ([Environment]::NewLine + [Environment]::NewLine))

	partition $TableName = m
		mode: import
		source =
				let
				    Source = Csv.Document(File.Contents(DataRoot & "\$FileName"), [Delimiter=",", Columns=$($Columns.Count), Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
				    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
				    $changedType$extra
				in
				    $PowerQueryOutputStep
"@
}

function New-ColumnSpec {
    param(
        [string]$Name,
        [ValidateSet('string', 'int64', 'double', 'dateTime')][string]$Type = 'string',
        [ValidateSet('none', 'sum', 'average', 'count')][string]$Summarize = 'none',
        [string]$Format = '',
        [bool]$Hidden = $false,
        [string]$Source = ''
    )
    if (-not $Source) { $Source = $Name.Trim("'") }
    [pscustomobject]@{
        Name = $Name
        Source = $Source
        Type = $Type
        Summarize = $Summarize
        Format = $Format
        Hidden = $Hidden
    }
}

[void][System.IO.Directory]::CreateDirectory($tablesRoot)
[void][System.IO.Directory]::CreateDirectory((Join-Path $reportRoot 'definition\pages'))

$pbip = [ordered]@{
    version = '1.0'
    artifacts = @([ordered]@{ report = [ordered]@{ path = "$modelName.Report" } })
    settings = [ordered]@{ enableAutoRecovery = $true }
}
Write-JsonFile (Join-Path $projectRoot "$modelName.pbip") $pbip

Write-JsonFile (Join-Path $modelRoot '.platform') ([ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json'
    metadata = [ordered]@{ type = 'SemanticModel'; displayName = $modelName }
    config = [ordered]@{ version = '2.0'; logicalId = '9e75b84c-9f93-4bc4-8a4d-865b27f16c9e' }
})
Write-JsonFile (Join-Path $modelRoot 'definition.pbism') ([ordered]@{ version = '4.2'; settings = [ordered]@{} })
Write-Utf8File (Join-Path $definitionRoot 'database.tmdl') "database`n`tcompatibilityLevel: 1606"

$modelTmdl = @"
model Model
	culture: zh-CN
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: zh-CN
	valueFilterBehavior: independent
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0
annotation PBI_ProTooling = ["DevMode"]
annotation PBI_QueryOrder = ["olist_business_overview","olist_monthly_performance","olist_category_performance","olist_customer_rfm","olist_customer_segments","olist_metric_definitions","DataRoot"]

ref table olist_business_overview
ref table olist_monthly_performance
ref table olist_category_performance
ref table olist_customer_rfm
ref table olist_customer_segments
ref table olist_metric_definitions
ref table 'KPI Measures'
"@
Write-Utf8File (Join-Path $definitionRoot 'model.tmdl') $modelTmdl

$escapedDataRoot = $BuildDataRoot.Replace('"', '""')
$expressionTmdl = @"
expression DataRoot = "$escapedDataRoot" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
	lineageTag: $(Get-LineageTag 'DataRoot')
	annotation PBI_NavigationStepName = Navigation
	annotation PBI_ResultType = Text
"@
Write-Utf8File (Join-Path $definitionRoot 'expressions.tmdl') $expressionTmdl

$overviewColumns = @(
    (New-ColumnSpec snapshot_id -Hidden $true),
    (New-ColumnSpec as_of_date dateTime),
    (New-ColumnSpec order_scope -Hidden $true),
    (New-ColumnSpec total_placed_orders int64 sum '#,0'),
    (New-ColumnSpec orders int64 sum '#,0'),
    (New-ColumnSpec purchasing_customers int64 sum '#,0'),
    (New-ColumnSpec repeat_customers int64 sum '#,0'),
    (New-ColumnSpec repeat_purchase_rate double average '0.00%'),
    (New-ColumnSpec merchandise_gmv_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec paid_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec units_sold int64 sum '#,0'),
    (New-ColumnSpec freight_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec aov_brl double average '#,0.00 "BRL"'),
    (New-ColumnSpec average_review_score double average '0.00'),
    (New-ColumnSpec canceled_orders int64 sum '#,0'),
    (New-ColumnSpec cancel_rate double average '0.00%'),
    (New-ColumnSpec currency_code -Hidden $true),
    (New-ColumnSpec data_mode -Hidden $true),
    (New-ColumnSpec _analytics_build_id -Hidden $true),
    (New-ColumnSpec _built_at -Hidden $true)
)
Write-Utf8File (Join-Path $tablesRoot 'olist_business_overview.tmdl') (New-TmdlTable -TableName 'olist_business_overview' -FileName 'olist_business_overview.csv' -Columns $overviewColumns -Description 'Olist all-time KPI snapshot; delivered orders are the sales scope and monetary values are BRL.')

$monthlyColumns = @(
    (New-ColumnSpec month_key),
    (New-ColumnSpec total_placed_orders int64 sum '#,0'),
    (New-ColumnSpec orders int64 sum '#,0'),
    (New-ColumnSpec purchasing_customers int64 sum '#,0'),
    (New-ColumnSpec merchandise_gmv_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec paid_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec units_sold int64 sum '#,0'),
    (New-ColumnSpec freight_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec aov_brl double average '#,0.00 "BRL"'),
    (New-ColumnSpec average_review_score double average '0.00'),
    (New-ColumnSpec canceled_orders int64 sum '#,0'),
    (New-ColumnSpec cancel_rate double average '0.00%'),
    (New-ColumnSpec currency_code -Hidden $true),
    (New-ColumnSpec data_mode -Hidden $true),
    (New-ColumnSpec _analytics_build_id -Hidden $true),
    (New-ColumnSpec _built_at -Hidden $true)
)
Write-Utf8File (Join-Path $tablesRoot 'olist_monthly_performance.tmdl') (New-TmdlTable -TableName 'olist_monthly_performance' -FileName 'olist_monthly_performance.csv' -Columns $monthlyColumns -Description 'Monthly Olist performance mart using purchase month and the documented delivered-order sales scope.')

$categoryColumns = @(
    (New-ColumnSpec category_id -Hidden $true),
    (New-ColumnSpec category_pt),
    (New-ColumnSpec category_en),
    (New-ColumnSpec category_display_name),
    (New-ColumnSpec category_translation_status),
    (New-ColumnSpec orders int64 sum '#,0'),
    (New-ColumnSpec units_sold int64 sum '#,0'),
    (New-ColumnSpec merchandise_gmv_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec average_item_price_brl double average '#,0.00 "BRL"'),
    (New-ColumnSpec freight_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec freight_ratio double average '0.00%'),
    (New-ColumnSpec average_review_score double average '0.00'),
    (New-ColumnSpec low_rating_rate double average '0.00%'),
    (New-ColumnSpec currency_code -Hidden $true),
    (New-ColumnSpec data_mode -Hidden $true),
    (New-ColumnSpec _analytics_build_id -Hidden $true),
    (New-ColumnSpec _built_at -Hidden $true)
)
Write-Utf8File (Join-Path $tablesRoot 'olist_category_performance.tmdl') (New-TmdlTable -TableName 'olist_category_performance' -FileName 'olist_category_performance.csv' -Columns $categoryColumns -Description 'Delivered-order category performance mart with item value, freight and attributed order-level review metrics.')

$rfmColumns = @(
    (New-ColumnSpec customer_unique_id),
    (New-ColumnSpec as_of_date dateTime -Hidden $true),
    (New-ColumnSpec last_purchase_date dateTime),
    (New-ColumnSpec recency_days int64 average '#,0'),
    (New-ColumnSpec frequency int64 average '0.00'),
    (New-ColumnSpec monetary_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec orders_per_customer double average '0.00'),
    (New-ColumnSpec is_repeat_customer int64 sum '#,0'),
    (New-ColumnSpec r_score int64 average '0'),
    (New-ColumnSpec f_score int64 average '0'),
    (New-ColumnSpec m_score int64 average '0'),
    (New-ColumnSpec rfm_score int64 average '0'),
    (New-ColumnSpec rfm_segment),
    (New-ColumnSpec currency_code -Hidden $true),
    (New-ColumnSpec data_mode -Hidden $true),
    (New-ColumnSpec _analytics_build_id -Hidden $true),
    (New-ColumnSpec _built_at -Hidden $true)
)
Write-Utf8File (Join-Path $tablesRoot 'olist_customer_rfm.tmdl') (New-TmdlTable -TableName 'olist_customer_rfm' -FileName 'olist_customer_rfm.csv' -Columns $rfmColumns -Description 'One row per purchasing customer_unique_id with deterministic RFM values and segments.')

$segmentColumns = @(
    (New-ColumnSpec rfm_segment),
    (New-ColumnSpec customers int64 sum '#,0'),
    (New-ColumnSpec repeat_customers int64 sum '#,0'),
    (New-ColumnSpec repeat_purchase_rate double average '0.00%'),
    (New-ColumnSpec average_recency_days double average '0.00'),
    (New-ColumnSpec average_frequency double average '0.00'),
    (New-ColumnSpec total_monetary_value_brl double sum '#,0.00 "BRL"'),
    (New-ColumnSpec average_monetary_value_brl double average '#,0.00 "BRL"'),
    (New-ColumnSpec customer_share double average '0.00%'),
    (New-ColumnSpec currency_code -Hidden $true),
    (New-ColumnSpec data_mode -Hidden $true),
    (New-ColumnSpec _analytics_build_id -Hidden $true),
    (New-ColumnSpec _built_at -Hidden $true)
)
Write-Utf8File (Join-Path $tablesRoot 'olist_customer_segments.tmdl') (New-TmdlTable -TableName 'olist_customer_segments' -FileName 'olist_customer_segments.csv' -Columns $segmentColumns -Description 'RFM segment summary derived from customer_unique_id-level customer values.')

$definitionColumns = @(
    (New-ColumnSpec metric_name),
    (New-ColumnSpec display_name),
    (New-ColumnSpec definition),
    (New-ColumnSpec formula),
    (New-ColumnSpec order_scope),
    (New-ColumnSpec grain),
    (New-ColumnSpec source_fields),
    (New-ColumnSpec currency_code),
    (New-ColumnSpec _analytics_build_id -Hidden $true),
    (New-ColumnSpec _built_at -Hidden $true)
)
Write-Utf8File (Join-Path $tablesRoot 'olist_metric_definitions.tmdl') (New-TmdlTable -TableName 'olist_metric_definitions' -FileName 'olist_metric_definitions.csv' -Columns $definitionColumns -Description 'Auditable English metric names, formulas, grains, scopes and source fields for the Olist analytics layer.')

$measureTmdl = @"
/// Measures used only by the Olist V2 report. Unsupported advertising, profit and cost metrics are intentionally absent.
table 'KPI Measures'
	lineageTag: $(Get-LineageTag 'KPI Measures')

	measure 'Merchandise GMV' = SUM(olist_business_overview[merchandise_gmv_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Merchandise GMV')

	measure Orders = SUM(olist_business_overview[orders])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Orders')

	measure 'Purchasing Customers' = SUM(olist_business_overview[purchasing_customers])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Purchasing Customers')

	measure 'Repeat Customers' = SUM(olist_business_overview[repeat_customers])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Repeat Customers')

	measure AOV = AVERAGE(olist_business_overview[aov_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/AOV')

	measure 'Repeat Purchase Rate' = AVERAGE(olist_business_overview[repeat_purchase_rate])
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/Repeat Purchase Rate')

	measure 'Average Review Score' = AVERAGE(olist_business_overview[average_review_score])
		formatString: 0.00
		lineageTag: $(Get-LineageTag 'measure/Average Review Score')

	measure 'Canceled Orders' = SUM(olist_business_overview[canceled_orders])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Canceled Orders')

	measure 'Cancel Rate' = AVERAGE(olist_business_overview[cancel_rate])
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/Cancel Rate')

	measure 'Freight Value' = SUM(olist_business_overview[freight_value_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Freight Value')

	measure 'Freight Ratio' = DIVIDE([Freight Value], [Merchandise GMV])
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/Freight Ratio')

	measure 'Monthly GMV' = SUM(olist_monthly_performance[merchandise_gmv_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Monthly GMV')

	measure 'Monthly Orders' = SUM(olist_monthly_performance[orders])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Monthly Orders')

	measure 'Monthly Average Review Score' = AVERAGE(olist_monthly_performance[average_review_score])
		formatString: 0.00
		lineageTag: $(Get-LineageTag 'measure/Monthly Average Review Score')

	measure 'Monthly Cancel Rate' = DIVIDE(SUM(olist_monthly_performance[canceled_orders]), SUM(olist_monthly_performance[total_placed_orders]))
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/Monthly Cancel Rate')

	measure 'Category GMV' = SUM(olist_category_performance[merchandise_gmv_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Category GMV')

	measure 'Category Orders' = SUM(olist_category_performance[orders])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Category Orders')

	measure 'Units Sold' = SUM(olist_category_performance[units_sold])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/Units Sold')

	measure 'Average Item Price' = AVERAGE(olist_category_performance[average_item_price_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Average Item Price')

	measure 'Category Freight Value' = SUM(olist_category_performance[freight_value_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Category Freight Value')

	measure 'Category Freight Ratio' = DIVIDE([Category Freight Value], [Category GMV])
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/Category Freight Ratio')

	measure 'Category Average Review Score' = AVERAGE(olist_category_performance[average_review_score])
		formatString: 0.00
		lineageTag: $(Get-LineageTag 'measure/Category Average Review Score')

	measure 'Category Low Rating Rate' = AVERAGE(olist_category_performance[low_rating_rate])
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/Category Low Rating Rate')

	measure 'RFM Customers' = DISTINCTCOUNT(olist_customer_rfm[customer_unique_id])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/RFM Customers')

	measure 'RFM Repeat Customers' = SUM(olist_customer_rfm[is_repeat_customer])
		formatString: #,0
		lineageTag: $(Get-LineageTag 'measure/RFM Repeat Customers')

	measure 'RFM Repeat Rate' = DIVIDE([RFM Repeat Customers], [RFM Customers])
		formatString: 0.00%
		lineageTag: $(Get-LineageTag 'measure/RFM Repeat Rate')

	measure 'Average Recency' = AVERAGE(olist_customer_rfm[recency_days])
		formatString: #,0.00
		lineageTag: $(Get-LineageTag 'measure/Average Recency')

	measure 'Average Frequency' = AVERAGE(olist_customer_rfm[frequency])
		formatString: 0.00
		lineageTag: $(Get-LineageTag 'measure/Average Frequency')

	measure 'Average Monetary' = AVERAGE(olist_customer_rfm[monetary_value_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Average Monetary')

	measure 'Customer Monetary Value' = SUM(olist_customer_rfm[monetary_value_brl])
		formatString: #,0.00 "BRL"
		lineageTag: $(Get-LineageTag 'measure/Customer Monetary Value')

	measure 'Overview Insight Text' = "Olist 公开数据包含 " & FORMAT([Orders], "#,0") & " 个 delivered 订单，商品成交额 " & FORMAT([Merchandise GMV] / 1000000, "0.00") & "M BRL；复购率 " & FORMAT([Repeat Purchase Rate], "0.00%") & "。"
		lineageTag: $(Get-LineageTag 'measure/Overview Insight Text')

	measure 'Category Insight Text' = VAR T = TOPN(1, ADDCOLUMNS(ALLSELECTED(olist_category_performance[category_display_name]), "__GMV", [Category GMV]), [__GMV], DESC, olist_category_performance[category_display_name], ASC) RETURN MAXX(T, olist_category_performance[category_display_name]) & " 为当前范围商品成交额最高品类，成交额 " & FORMAT(MAXX(T, [__GMV]) / 1000000, "0.00") & "M BRL。"
		lineageTag: $(Get-LineageTag 'measure/Category Insight Text')

	measure 'Customer Insight Text' = "客户分析按 customer_unique_id 统一身份；" & FORMAT([RFM Customers], "#,0") & " 位购买客户中，" & FORMAT([RFM Repeat Customers], "#,0") & " 位至少完成两笔 delivered 订单。"
		lineageTag: $(Get-LineageTag 'measure/Customer Insight Text')

	measure 'Experience Insight Text' = VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALL(olist_category_performance[category_display_name]), "__Low", [Category Low Rating Rate], "__Orders", [Category Orders]), [__Orders] >= 1000), [__Low], DESC, olist_category_performance[category_display_name], ASC) RETURN "评价、取消与运费指标来自现有真实 mart；千单以上品类中，" & MAXX(T, olist_category_performance[category_display_name]) & " 的低评分占比最高，为 " & FORMAT(MAXX(T, [__Low]), "0.00%") & "。"
		lineageTag: $(Get-LineageTag 'measure/Experience Insight Text')

	column Dummy
		dataType: string
		isHidden
		lineageTag: $(Get-LineageTag 'KPI Measures/Dummy')
		summarizeBy: none
		sourceColumn: [Dummy]

	partition 'KPI Measures' = calculated
		mode: import
		source = ROW("Dummy", BLANK())
"@
Write-Utf8File (Join-Path $tablesRoot 'KPI Measures.tmdl') $measureTmdl

Write-Host "Olist semantic model generated: $modelRoot"
Write-Host 'Tables: 6 imported marts plus one measure table; no relationships or unsupported advertising/profit measures.'
