[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$ServerPort,

    [Parameter(Mandatory = $true)]
    [string]$DatabaseName,

    [string]$PowerBIBin = 'D:\Bin',

    [switch]$ForceReplace
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if ((Split-Path $repoRoot -Leaf) -ne 'Ecommerce-Operations-Analytics-Assistant') {
    throw "Unexpected repository root: $repoRoot"
}

$dataRoot = Join-Path $repoRoot 'dashboard\powerbi_data'
$requiredFiles = 'products.csv', 'users.csv', 'orders.csv', 'ads.csv', 'calendar.csv'
foreach ($file in $requiredFiles) {
    $path = Join-Path $dataRoot $file
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Power BI input is missing: $path"
    }
}

$tomAssembly = Join-Path $PowerBIBin 'Microsoft.PowerBI.Tabular.dll'
if (-not (Test-Path -LiteralPath $tomAssembly -PathType Leaf)) {
    throw "Power BI TOM assembly was not found: $tomAssembly"
}
[void][Reflection.Assembly]::LoadFrom($tomAssembly)

function ConvertTo-MPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return $Path.Replace('"', '""')
}

function Add-ModelTable {
    param(
        [Parameter(Mandatory = $true)]$Model,
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Description,
        [string]$DataCategory
    )

    $table = [Microsoft.AnalysisServices.Tabular.Table]::new()
    $table.Name = $Name
    if ($Description) { $table.Description = $Description }
    if ($DataCategory) { $table.DataCategory = $DataCategory }
    $Model.Tables.Add($table)
    return $table
}

function Add-DataColumn {
    param(
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][Microsoft.AnalysisServices.Tabular.DataType]$DataType,
        [string]$SourceColumn = $Name,
        [Microsoft.AnalysisServices.Tabular.AggregateFunction]$SummarizeBy = [Microsoft.AnalysisServices.Tabular.AggregateFunction]::None,
        [string]$FormatString,
        [string]$DataCategory,
        [string]$Description,
        [switch]$Hidden
    )

    $column = [Microsoft.AnalysisServices.Tabular.DataColumn]::new()
    $column.Name = $Name
    $column.SourceColumn = $SourceColumn
    $column.DataType = $DataType
    $column.SummarizeBy = $SummarizeBy
    if ($FormatString) { $column.FormatString = $FormatString }
    if ($DataCategory) { $column.DataCategory = $DataCategory }
    if ($Description) { $column.Description = $Description }
    $column.IsHidden = $Hidden.IsPresent
    $Table.Columns.Add($column)
    return $column
}

function Add-MPartition {
    param(
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][string]$Expression
    )

    $source = [Microsoft.AnalysisServices.Tabular.MPartitionSource]::new()
    $source.Expression = $Expression
    $partition = [Microsoft.AnalysisServices.Tabular.Partition]::new()
    $partition.Name = $Table.Name
    $partition.Mode = [Microsoft.AnalysisServices.Tabular.ModeType]::Import
    $partition.Source = $source
    $Table.Partitions.Add($partition)
}

function Add-Measure {
    param(
        [Parameter(Mandatory = $true)]$Table,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Expression,
        [string]$FormatString,
        [string]$Description
    )

    $measure = [Microsoft.AnalysisServices.Tabular.Measure]::new()
    $measure.Name = $Name
    $measure.Expression = $Expression
    if ($FormatString) { $measure.FormatString = $FormatString }
    if ($Description) { $measure.Description = $Description }
    $Table.Measures.Add($measure)
}

function Add-Relationship {
    param(
        [Parameter(Mandatory = $true)]$Model,
        [Parameter(Mandatory = $true)]$FromColumn,
        [Parameter(Mandatory = $true)]$ToColumn
    )

    $relationship = [Microsoft.AnalysisServices.Tabular.SingleColumnRelationship]::new()
    $relationship.Name = [guid]::NewGuid().ToString()
    $relationship.FromColumn = $FromColumn
    $relationship.ToColumn = $ToColumn
    $relationship.FromCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::Many
    $relationship.ToCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::One
    $relationship.CrossFilteringBehavior = [Microsoft.AnalysisServices.Tabular.CrossFilteringBehavior]::OneDirection
    $Model.Relationships.Add($relationship)
}

$server = [Microsoft.AnalysisServices.Tabular.Server]::new()
try {
    $server.Connect("localhost:$ServerPort")
    $database = $server.Databases.FindByName($DatabaseName)
    if ($null -eq $database) {
        throw "Power BI model database was not found: $DatabaseName"
    }

    $model = $database.Model
    if ($model.Tables.Count -gt 0 -and -not $ForceReplace) {
        throw "The target model already contains $($model.Tables.Count) tables. Re-run with -ForceReplace only after confirming the target PBIX."
    }
    if ($model.Tables.Count -gt 0) {
        $existing = @($model.Tables | ForEach-Object { $_ })
        foreach ($table in $existing) { $model.Tables.Remove($table) }
        $model.SaveChanges()
    }

    $productsPath = ConvertTo-MPath (Join-Path $dataRoot 'products.csv')
    $usersPath = ConvertTo-MPath (Join-Path $dataRoot 'users.csv')
    $ordersPath = ConvertTo-MPath (Join-Path $dataRoot 'orders.csv')
    $adsPath = ConvertTo-MPath (Join-Path $dataRoot 'ads.csv')
    $calendarPath = ConvertTo-MPath (Join-Path $dataRoot 'calendar.csv')

    $products = Add-ModelTable $model 'products' 'Synthetic compliant sample product catalog for portfolio demonstration.'
    $productId = Add-DataColumn $products 'product_id' String -Description 'Synthetic product key.'
    Add-DataColumn $products 'product_name' String | Out-Null
    Add-DataColumn $products 'category' String | Out-Null
    Add-DataColumn $products 'price' Int64 -SummarizeBy Average -FormatString '#,0 "TWD"' | Out-Null
    Add-DataColumn $products 'price_band' String | Out-Null
    Add-DataColumn $products 'sold_count' Int64 -SummarizeBy Sum -FormatString '#,0' | Out-Null
    Add-DataColumn $products 'rating' Double -SummarizeBy Average -FormatString '0.00' | Out-Null
    Add-DataColumn $products 'review_count' Int64 -SummarizeBy Sum -FormatString '#,0' | Out-Null
    Add-DataColumn $products 'shop_name' String | Out-Null
    Add-DataColumn $products 'location' String -DataCategory 'City' | Out-Null
    Add-DataColumn $products 'crawl_time' String | Out-Null
    Add-DataColumn $products 'source_url' String -DataCategory 'WebUrl' | Out-Null
    Add-DataColumn $products 'data_source_type' String | Out-Null
    Add-DataColumn $products 'hot_score' Double -SummarizeBy Average -FormatString '0.00' | Out-Null
    Add-DataColumn $products 'opportunity_score' Double -SummarizeBy Average -FormatString '0.00' | Out-Null
    Add-MPartition $products @"
let
    Source = Csv.Document(File.Contents("$productsPath"), [Delimiter=",", Columns=14, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"product_id", type text}, {"product_name", type text}, {"category", type text}, {"price", Int64.Type}, {"sold_count", Int64.Type}, {"rating", type number}, {"review_count", Int64.Type}, {"shop_name", type text}, {"location", type text}, {"crawl_time", type text}, {"source_url", type text}, {"data_source_type", type text}, {"hot_score", type number}, {"opportunity_score", type number}}, "en-US"),
    #"Added Price Band" = Table.AddColumn(#"Changed Type", "price_band", each if [price] <= 100 then "0-100" else if [price] <= 300 then "101-300" else if [price] <= 500 then "301-500" else "501+", type text)
in
    #"Added Price Band"
"@

    $users = Add-ModelTable $model 'users' 'Synthetic customer dimension with FY2025 RFM attributes.'
    $userId = Add-DataColumn $users 'user_id' String -Description 'Synthetic user key.'
    Add-DataColumn $users 'age_group' String | Out-Null
    Add-DataColumn $users 'region' String -DataCategory 'City' | Out-Null
    Add-DataColumn $users 'register_date' DateTime -FormatString 'yyyy-mm-dd' | Out-Null
    Add-DataColumn $users 'acquisition_channel' String | Out-Null
    Add-DataColumn $users 'repeat_propensity' Double -SummarizeBy Average -FormatString '0.0%' | Out-Null
    Add-DataColumn $users 'data_source_type' String | Out-Null
    Add-DataColumn $users 'recency' Int64 -SummarizeBy Average -FormatString '#,0' | Out-Null
    Add-DataColumn $users 'frequency' Int64 -SummarizeBy Average -FormatString '0.0' | Out-Null
    Add-DataColumn $users 'monetary' Double -SummarizeBy Average -FormatString '#,0 "TWD"' | Out-Null
    Add-DataColumn $users 'r_score' Int64 -SummarizeBy Average -FormatString '0' | Out-Null
    Add-DataColumn $users 'f_score' Int64 -SummarizeBy Average -FormatString '0' | Out-Null
    Add-DataColumn $users 'm_score' Int64 -SummarizeBy Average -FormatString '0' | Out-Null
    Add-DataColumn $users 'rfm_segment' String | Out-Null
    Add-DataColumn $users 'customer_type' String | Out-Null
    Add-MPartition $users @"
let
    Source = Csv.Document(File.Contents("$usersPath"), [Delimiter=",", Columns=14, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"user_id", type text}, {"age_group", type text}, {"region", type text}, {"register_date", type date}, {"acquisition_channel", type text}, {"repeat_propensity", type number}, {"data_source_type", type text}, {"recency", Int64.Type}, {"frequency", Int64.Type}, {"monetary", type number}, {"r_score", Int64.Type}, {"f_score", Int64.Type}, {"m_score", Int64.Type}, {"rfm_segment", type text}}, "en-US"),
    #"Added Customer Type" = Table.AddColumn(#"Changed Type", "customer_type", each if [frequency] = null then "No Purchase" else if [frequency] >= 2 then "Repeat" else "New", type text)
in
    #"Added Customer Type"
"@

    $orders = Add-ModelTable $model 'orders' 'Synthetic order fact table; monetary values are TWD.'
    Add-DataColumn $orders 'order_id' String | Out-Null
    $orderUserId = Add-DataColumn $orders 'user_id' String -Hidden
    $orderProductId = Add-DataColumn $orders 'product_id' String -Hidden
    $orderDate = Add-DataColumn $orders 'order_date' DateTime -FormatString 'yyyy-mm-dd' -Hidden
    Add-DataColumn $orders 'quantity' Int64 -SummarizeBy Sum -FormatString '#,0' | Out-Null
    Add-DataColumn $orders 'unit_price' Double -SummarizeBy Average -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $orders 'discount_amount' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $orders 'gross_amount' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $orders 'refund_amount' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $orders 'net_sales' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $orders 'cost' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $orders 'status' String | Out-Null
    Add-DataColumn $orders 'currency' String | Out-Null
    Add-DataColumn $orders 'data_source_type' String | Out-Null
    Add-MPartition $orders @"
let
    Source = Csv.Document(File.Contents("$ordersPath"), [Delimiter=",", Columns=14, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"order_id", type text}, {"user_id", type text}, {"product_id", type text}, {"order_date", type date}, {"quantity", Int64.Type}, {"unit_price", type number}, {"discount_amount", type number}, {"gross_amount", type number}, {"refund_amount", type number}, {"net_sales", type number}, {"cost", type number}, {"status", type text}, {"currency", type text}, {"data_source_type", type text}}, "en-US")
in
    #"Changed Type"
"@

    $ads = Add-ModelTable $model 'ads' 'Synthetic daily advertising performance fact table; monetary values are TWD.'
    $adsDate = Add-DataColumn $ads 'date' DateTime -FormatString 'yyyy-mm-dd' -Hidden
    Add-DataColumn $ads 'campaign_id' String | Out-Null
    Add-DataColumn $ads 'campaign_name' String | Out-Null
    Add-DataColumn $ads 'channel' String | Out-Null
    Add-DataColumn $ads 'impressions' Int64 -SummarizeBy Sum -FormatString '#,0' | Out-Null
    Add-DataColumn $ads 'clicks' Int64 -SummarizeBy Sum -FormatString '#,0' | Out-Null
    Add-DataColumn $ads 'spend' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $ads 'conversions' Int64 -SummarizeBy Sum -FormatString '#,0' | Out-Null
    Add-DataColumn $ads 'attributed_revenue' Double -SummarizeBy Sum -FormatString '#,0.00 "TWD"' | Out-Null
    Add-DataColumn $ads 'currency' String | Out-Null
    Add-DataColumn $ads 'data_source_type' String | Out-Null
    Add-MPartition $ads @"
let
    Source = Csv.Document(File.Contents("$adsPath"), [Delimiter=",", Columns=11, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"date", type date}, {"campaign_id", type text}, {"campaign_name", type text}, {"channel", type text}, {"impressions", Int64.Type}, {"clicks", Int64.Type}, {"spend", type number}, {"conversions", Int64.Type}, {"attributed_revenue", type number}, {"currency", type text}, {"data_source_type", type text}}, "en-US")
in
    #"Changed Type"
"@

    $calendar = Add-ModelTable $model 'calendar' 'Dedicated continuous date dimension for 2025 reporting.' 'Time'
    $calendarDate = Add-DataColumn $calendar 'date' DateTime -FormatString 'yyyy-mm-dd'
    $calendarYear = Add-DataColumn $calendar 'year' Int64 -FormatString '0'
    $calendarQuarter = Add-DataColumn $calendar 'quarter' String
    $calendarMonth = Add-DataColumn $calendar 'month' String
    $calendarMonthSort = Add-DataColumn $calendar 'month_sort' Int64 -FormatString '0' -Hidden
    Add-DataColumn $calendar 'week' Int64 -FormatString '0' | Out-Null
    Add-DataColumn $calendar 'weekday' String | Out-Null
    Add-DataColumn $calendar 'is_weekend' Int64 -FormatString '0' | Out-Null
    Add-DataColumn $calendar 'is_promotion' Int64 -FormatString '0' | Out-Null
    $calendarMonth.SortByColumn = $calendarMonthSort
    Add-MPartition $calendar @"
let
    Source = Csv.Document(File.Contents("$calendarPath"), [Delimiter=",", Columns=8, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"date", type date}, {"year", Int64.Type}, {"quarter", type text}, {"month", type text}, {"week", Int64.Type}, {"weekday", type text}, {"is_weekend", Int64.Type}, {"is_promotion", Int64.Type}}, "en-US"),
    #"Added Month Sort" = Table.AddColumn(#"Changed Type", "month_sort", each [year] * 100 + Date.Month([date]), Int64.Type)
in
    #"Added Month Sort"
"@

    $dateHierarchy = [Microsoft.AnalysisServices.Tabular.Hierarchy]::new()
    $dateHierarchy.Name = 'Date Hierarchy'
    $calendar.Hierarchies.Add($dateHierarchy)
    $levelOrdinal = 0
    foreach ($levelSpec in @(
        @{ Name = 'Year'; Column = $calendarYear },
        @{ Name = 'Quarter'; Column = $calendarQuarter },
        @{ Name = 'Month'; Column = $calendarMonth },
        @{ Name = 'Date'; Column = $calendarDate }
    )) {
        $level = [Microsoft.AnalysisServices.Tabular.Level]::new()
        $level.Name = $levelSpec.Name
        $level.Column = $levelSpec.Column
        $level.Ordinal = $levelOrdinal
        $dateHierarchy.Levels.Add($level)
        $levelOrdinal++
    }

    $measures = Add-ModelTable $model 'KPI Measures' 'Central measure table. All portfolio KPIs are defined here.'
    $calculatedSource = [Microsoft.AnalysisServices.Tabular.CalculatedPartitionSource]::new()
    $calculatedSource.Expression = 'ROW("Dummy", BLANK())'
    $calculatedPartition = [Microsoft.AnalysisServices.Tabular.Partition]::new()
    $calculatedPartition.Name = 'KPI Measures'
    $calculatedPartition.Mode = [Microsoft.AnalysisServices.Tabular.ModeType]::Import
    $calculatedPartition.Source = $calculatedSource
    $measures.Partitions.Add($calculatedPartition)
    $dummy = [Microsoft.AnalysisServices.Tabular.CalculatedTableColumn]::new()
    $dummy.Name = 'Dummy'
    $dummy.SourceColumn = '[Dummy]'
    $dummy.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
    $dummy.IsHidden = $true
    $dummy.SummarizeBy = [Microsoft.AnalysisServices.Tabular.AggregateFunction]::None
    $measures.Columns.Add($dummy)

    Add-Measure $measures 'GMV' 'CALCULATE(SUM(orders[gross_amount]), orders[status] IN {"completed", "refunded"})' '#,0 "TWD"' 'Gross merchandise value before discounts and refunds for completed or refunded orders.'
    Add-Measure $measures 'Net Sales' 'CALCULATE(SUM(orders[net_sales]), orders[status] = "completed")' '#,0 "TWD"' 'Recognized completed-order sales after discount; cancelled and refunded orders are excluded.'
    Add-Measure $measures 'Completed Orders' 'CALCULATE(DISTINCTCOUNT(orders[order_id]), orders[status] = "completed")' '#,0'
    Add-Measure $measures 'Gross Profit' '[Net Sales] - CALCULATE(SUM(orders[cost]), orders[status] = "completed")' '#,0 "TWD"'
    Add-Measure $measures 'Gross Margin %' 'DIVIDE([Gross Profit], [Net Sales])' '0.0%'
    Add-Measure $measures 'AOV' 'DIVIDE([Net Sales], [Completed Orders])' '#,0 "TWD"'
    Add-Measure $measures 'Purchasing Users' 'CALCULATE(DISTINCTCOUNT(orders[user_id]), orders[status] = "completed")' '#,0'
    Add-Measure $measures 'Registered Users' 'DISTINCTCOUNT(users[user_id])' '#,0'
    Add-Measure $measures 'Purchasing Users FY2025' 'CALCULATE([Purchasing Users], REMOVEFILTERS(calendar), DATESBETWEEN(calendar[date], DATE(2025, 1, 1), DATE(2025, 12, 31)))' '#,0'
    Add-Measure $measures 'Repeat Users FY2025' 'COUNTROWS(FILTER(CALCULATETABLE(VALUES(orders[user_id]), REMOVEFILTERS(calendar), DATESBETWEEN(calendar[date], DATE(2025, 1, 1), DATE(2025, 12, 31)), orders[status] = "completed"), CALCULATE(DISTINCTCOUNT(orders[order_id]), REMOVEFILTERS(calendar), DATESBETWEEN(calendar[date], DATE(2025, 1, 1), DATE(2025, 12, 31)), orders[status] = "completed") >= 2))' '#,0'
    Add-Measure $measures 'Repeat Rate FY2025 %' 'DIVIDE([Repeat Users FY2025], [Purchasing Users FY2025])' '0.0%'
    Add-Measure $measures 'Product Count' 'DISTINCTCOUNT(products[product_id])' '#,0'
    Add-Measure $measures 'High Opportunity Products' 'CALCULATE(DISTINCTCOUNT(products[product_id]), products[opportunity_score] >= 70)' '#,0'
    Add-Measure $measures 'Units Sold' 'CALCULATE(SUM(orders[quantity]), orders[status] = "completed")' '#,0'
    Add-Measure $measures 'Average Recency' 'AVERAGE(users[recency])' '#,0'
    Add-Measure $measures 'Average Frequency' 'AVERAGE(users[frequency])' '0.0'
    Add-Measure $measures 'Average Monetary' 'AVERAGE(users[monetary])' '#,0 "TWD"'
    Add-Measure $measures 'New Customers' 'CALCULATE(DISTINCTCOUNT(users[user_id]), users[customer_type] = "New")' '#,0'
    Add-Measure $measures 'Repeat Customers' 'CALCULATE(DISTINCTCOUNT(users[user_id]), users[customer_type] = "Repeat")' '#,0'
    Add-Measure $measures 'Impressions' 'SUM(ads[impressions])' '#,0'
    Add-Measure $measures 'Clicks' 'SUM(ads[clicks])' '#,0'
    Add-Measure $measures 'Ad Spend' 'SUM(ads[spend])' '#,0 "TWD"'
    Add-Measure $measures 'Conversions' 'SUM(ads[conversions])' '#,0'
    Add-Measure $measures 'Attributed Revenue' 'SUM(ads[attributed_revenue])' '#,0 "TWD"'
    Add-Measure $measures 'CTR %' 'DIVIDE([Clicks], [Impressions])' '0.00%'
    Add-Measure $measures 'CVR %' 'DIVIDE([Conversions], [Clicks])' '0.00%'
    Add-Measure $measures 'CPC' 'DIVIDE([Ad Spend], [Clicks])' '#,0.00 "TWD"'
    Add-Measure $measures 'CPA' 'DIVIDE([Ad Spend], [Conversions])' '#,0.00 "TWD"'
    Add-Measure $measures 'ROAS' 'DIVIDE([Attributed Revenue], [Ad Spend])' '0.00x'
    Add-Measure $measures 'Net Sales PM' 'CALCULATE([Net Sales], DATEADD(calendar[date], -1, MONTH))' '#,0 "TWD"'
    Add-Measure $measures 'Net Sales MoM %' 'DIVIDE([Net Sales] - [Net Sales PM], [Net Sales PM])' '0.0%'
    Add-Measure $measures 'Average Hot Score' 'AVERAGE(products[hot_score])' '0.00' 'Average normalized product heat score in the current filter context.'
    Add-Measure $measures 'Average Opportunity Score' 'AVERAGE(products[opportunity_score])' '0.00' 'Average opportunity score; higher values indicate stronger demand with lower competition and price crowding.'
    Add-Measure $measures 'Top 10 Product Net Sales' 'VAR ProductRank = RANKX(ALLSELECTED(products[product_name]), [Net Sales],, DESC, DENSE) RETURN IF(ProductRank <= 10, [Net Sales])' '#,0 "TWD"' 'Net sales returned only for the ten highest-selling products in the current selection.'
    Add-Measure $measures 'Top 10 Product Gross Profit' 'VAR ProductRank = RANKX(ALLSELECTED(products[product_name]), [Net Sales],, DESC, DENSE) RETURN IF(ProductRank <= 10, [Gross Profit])' '#,0 "TWD"' 'Gross profit for the same ten products ranked by net sales.'
    Add-Measure $measures 'Top 10 Opportunity Score' 'VAR OpportunityRank = RANKX(ALLSELECTED(products[product_name]), [Average Opportunity Score],, DESC, DENSE) RETURN IF(OpportunityRank <= 10, [Average Opportunity Score])' '0.00' 'Opportunity score returned only for the ten highest-opportunity products in the current selection.'
    Add-Measure $measures 'Hot Score for Opportunity Top 10' 'VAR OpportunityRank = RANKX(ALLSELECTED(products[product_name]), [Average Opportunity Score],, DESC, DENSE) RETURN IF(OpportunityRank <= 10, [Average Hot Score])' '0.00' 'Hot score for the same ten products ranked by opportunity score.'

    Add-Relationship $model $orderProductId $productId
    Add-Relationship $model $orderUserId $userId
    Add-Relationship $model $orderDate $calendarDate
    Add-Relationship $model $adsDate $calendarDate

    $model.SaveChanges()
    Write-Host "Metadata saved: $($model.Tables.Count) tables, $($model.Relationships.Count) relationships."

    $model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $model.SaveChanges()
    Write-Host 'Full data refresh completed.'

    $model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate)
    $model.SaveChanges()
    Write-Host "Model calculation completed: $($measures.Measures.Count) measures."
}
finally {
    if ($server.Connected) { $server.Disconnect() }
}
