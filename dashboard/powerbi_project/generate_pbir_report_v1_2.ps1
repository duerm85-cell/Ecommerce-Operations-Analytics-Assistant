[CmdletBinding()]
param(
    [string]$BuildDataRoot = 'C:\path\to\Ecommerce-Operations-Analytics-Assistant\dashboard\powerbi_data'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$dashboardRoot = Split-Path -Parent $projectRoot
$reportRoot = Join-Path $projectRoot 'Ecommerce-Operations-Analytics-Assistant.Report'
$modelRoot = Join-Path $projectRoot 'Ecommerce-Operations-Analytics-Assistant.SemanticModel'
$pagesRoot = Join-Path $reportRoot 'definition\pages'
$measureTable = 'KPI Measures'
$visualSchema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json'
$pageSchema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json'
$themeSource = Join-Path $dashboardRoot 'powerbi_theme\executive_storytelling_v1.2.json'
$themeFileName = 'ExecutiveStorytellingV12-20260905.json'
$themeTarget = Join-Path $reportRoot "StaticResources\RegisteredResources\$themeFileName"

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

if (-not (Test-Path -LiteralPath (Join-Path $reportRoot 'definition.pbir'))) {
    throw "Power BI report project was not found: $reportRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $modelRoot 'definition.pbism'))) {
    throw "Power BI semantic model project was not found: $modelRoot"
}
if (-not (Test-Path -LiteralPath $themeSource)) {
    throw "V1.2 Power BI theme was not found: $themeSource"
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
    param([string]$Measure, [string]$DisplayName)
    $projection = [ordered]@{
        field = [ordered]@{
            Measure = [ordered]@{
                Expression = [ordered]@{ SourceRef = [ordered]@{ Entity = $measureTable } }
                Property = $Measure
            }
        }
        queryRef = "$measureTable.$Measure"
        nativeQueryRef = $Measure
    }
    if ($DisplayName) { $projection.displayName = $DisplayName }
    return $projection
}

function New-ColumnProjection {
    param([string]$Table, [string]$Column, [string]$DisplayName, [switch]$Active)
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
    if ($DisplayName) { $projection.displayName = $DisplayName }
    if ($Active) { $projection.active = $true }
    return $projection
}

function New-ContainerObjects {
    param([string]$Title, [switch]$HideTitle, [string]$Background = '#FFFFFF')
    return [ordered]@{
        title = @([ordered]@{ properties = [ordered]@{
            show = (New-Literal $(if ($HideTitle) { 'false' } else { 'true' }))
            text = (New-Literal "'$Title'")
            titleWrap = (New-Literal 'true')
            fontFamily = (New-Literal "'Microsoft YaHei'")
            fontSize = (New-Literal '13D')
            bold = (New-Literal 'true')
            fontColor = (New-SolidColor $colors.Ink)
        } })
        subTitle = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
        background = @([ordered]@{ properties = [ordered]@{
            show = (New-Literal 'true')
            color = (New-SolidColor $Background)
            transparency = (New-Literal '0D')
        } })
        border = @([ordered]@{ properties = [ordered]@{
            show = (New-Literal 'true')
            color = (New-SolidColor $colors.Border)
            radius = (New-Literal '8D')
        } })
        padding = @([ordered]@{ properties = [ordered]@{
            top = (New-Literal '8D')
            bottom = (New-Literal '8D')
            left = (New-Literal '10D')
            right = (New-Literal '10D')
        } })
        visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
    }
}

function Write-Visual {
    param([string]$PageName, [string]$Key, $Visual)
    $id = Get-StableId "$PageName/$Key"
    $Visual.name = $id
    Write-JsonFile (Join-Path $pagesRoot "$PageName\visuals\$id\visual.json") $Visual
    return $id
}

function New-Page {
    param([string]$Name, [string]$DisplayName)
    $pageDirectory = Join-Path $pagesRoot $Name
    $visualsDirectory = Join-Path $pageDirectory 'visuals'
    $resolvedPagesRoot = [System.IO.Path]::GetFullPath($pagesRoot).TrimEnd('\') + '\'
    $resolvedVisuals = [System.IO.Path]::GetFullPath($visualsDirectory)
    if (-not $resolvedVisuals.StartsWith($resolvedPagesRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clear visuals outside report pages: $resolvedVisuals"
    }
    if (Test-Path -LiteralPath $visualsDirectory) {
        Remove-Item -LiteralPath $visualsDirectory -Recurse -Force
    }
    [void][System.IO.Directory]::CreateDirectory($visualsDirectory)
    $page = [ordered]@{
        '$schema' = $pageSchema
        name = $Name
        displayName = $DisplayName
        displayOption = 'FitToPage'
        height = 810
        width = 1440
        objects = [ordered]@{
            background = @([ordered]@{ properties = [ordered]@{
                color = (New-SolidColor $colors.Page)
                transparency = (New-Literal '0D')
            } })
            outspace = @([ordered]@{ properties = [ordered]@{
                color = (New-SolidColor '#E8EDF3')
                transparency = (New-Literal '0D')
            } })
        }
    }
    Write-JsonFile (Join-Path $pageDirectory 'page.json') $page
}

function Add-Textbox {
    param(
        [string]$Page, [string]$Key, [string]$Text,
        [int]$X, [int]$Y, [int]$Width, [int]$Height,
        [string]$FontSize = '16px', [string]$Color = '#16324F',
        [string]$Background = '#F6F8FB', [switch]$Bold,
        [ValidateSet('left', 'center', 'right')][string]$Align = 'left', [int]$Z = 100
    )
    $textStyle = [ordered]@{ fontFamily = 'Microsoft YaHei'; fontSize = $FontSize; color = $Color }
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
                        horizontalTextAlignment = $Align
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
    [void](Write-Visual $Page $Key $visual)
}

function Add-KpiCard {
    param(
        [string]$Page, [string]$Key, [string]$Measure, [string]$Label,
        [int]$X, [int]$Y, [int]$Width, [int]$Height,
        [string]$Accent = '#2F80ED', [long]$DisplayUnits = 0, [int]$Precision = 0,
        [int]$FontSize = 24, [int]$Z = 220
    )
    $projection = New-MeasureProjection $Measure $Label
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = 'cardVisual'
            query = [ordered]@{ queryState = [ordered]@{ Data = [ordered]@{ projections = @($projection) } } }
            objects = [ordered]@{
                value = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    fontFamily = (New-Literal "'Segoe UI Semibold'")
                    fontSize = (New-Literal "${FontSize}D")
                    bold = (New-Literal 'true')
                    fontColor = (New-SolidColor $Accent)
                    horizontalAlignment = (New-Literal "'left'")
                    textWrap = (New-Literal 'true')
                    labelDisplayUnits = (New-Literal "${DisplayUnits}L")
                    labelPrecision = (New-Literal "${Precision}L")
                }; selector = [ordered]@{ id = 'default' } })
                label = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    fontFamily = (New-Literal "'Microsoft YaHei'")
                    fontSize = (New-Literal '11D')
                    bold = (New-Literal 'true')
                    fontColor = (New-SolidColor $colors.Muted)
                    textWrap = (New-Literal 'true')
                    position = (New-Literal "'aboveValue'")
                    horizontalAlignment = (New-Literal "'left'")
                }; selector = [ordered]@{ id = 'default' } })
                layout = @([ordered]@{ properties = [ordered]@{
                    alignment = (New-Literal "'top'")
                    paddingUniform = (New-Literal '2L')
                    topOuterMargin = (New-Literal '0L')
                    bottomOuterMargin = (New-Literal '0L')
                    leftOuterMargin = (New-Literal '0L')
                    rightOuterMargin = (New-Literal '0L')
                }; selector = [ordered]@{ id = 'default' } })
                outline = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') }; selector = [ordered]@{ id = 'default' } })
            }
            visualContainerObjects = (New-ContainerObjects '' -HideTitle)
        }
    }
    [void](Write-Visual $Page $Key $visual)
}

function Add-DynamicTextCard {
    param(
        [string]$Page, [string]$Key, [string]$Measure,
        [int]$X, [int]$Y, [int]$Width, [int]$Height,
        [string]$Background = '#EAF3FF', [string]$Color = '#16324F', [int]$FontSize = 17, [int]$Z = 210
    )
    $projection = New-MeasureProjection $Measure ''
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = 'cardVisual'
            query = [ordered]@{ queryState = [ordered]@{ Data = [ordered]@{ projections = @($projection) } } }
            objects = [ordered]@{
                value = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    fontFamily = (New-Literal "'Microsoft YaHei'")
                    fontSize = (New-Literal "${FontSize}D")
                    bold = (New-Literal 'true')
                    fontColor = (New-SolidColor $Color)
                    textWrap = (New-Literal 'true')
                    horizontalAlignment = (New-Literal "'left'")
                }; selector = [ordered]@{ id = 'default' } })
                label = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') }; selector = [ordered]@{ id = 'default' } })
                layout = @([ordered]@{ properties = [ordered]@{
                    paddingUniform = (New-Literal '4L')
                    topOuterMargin = (New-Literal '0L')
                    bottomOuterMargin = (New-Literal '0L')
                    leftOuterMargin = (New-Literal '0L')
                    rightOuterMargin = (New-Literal '0L')
                }; selector = [ordered]@{ id = 'default' } })
                outline = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') }; selector = [ordered]@{ id = 'default' } })
            }
            visualContainerObjects = (New-ContainerObjects '' -HideTitle -Background $Background)
        }
    }
    [void](Write-Visual $Page $Key $visual)
}

function Add-Slicer {
    param(
        [string]$Page, [string]$Key, [string]$Table, [string]$Column, [string]$Label,
        [int]$X, [int]$Y, [int]$Width, [int]$Height = 76,
        [ValidateSet('Dropdown', 'Between', 'Single')][string]$Mode = 'Dropdown',
        [string]$SyncGroup, [int]$Z = 300
    )
    $visualBody = [ordered]@{
        visualType = 'slicer'
        query = [ordered]@{ queryState = [ordered]@{ Values = [ordered]@{ projections = @((New-ColumnProjection $Table $Column '' )) } } }
        objects = [ordered]@{
            data = @([ordered]@{ properties = [ordered]@{ mode = (New-Literal "'$Mode'") } })
            header = @([ordered]@{ properties = [ordered]@{
                show = (New-Literal 'true')
                text = (New-Literal "'$Label'")
                fontFamily = (New-Literal "'Microsoft YaHei'")
                textSize = (New-Literal '10D')
                fontColor = (New-SolidColor $colors.Ink)
            } })
        }
        visualContainerObjects = (New-ContainerObjects '' -HideTitle)
    }
    if ($SyncGroup) { $visualBody.syncGroup = [ordered]@{ groupName = $SyncGroup; fieldChanges = $true; filterChanges = $true } }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = $visualBody
    }
    [void](Write-Visual $Page $Key $visual)
}

function New-ButtonState {
    param([string]$State, [string]$Color, [string]$TextColor, [switch]$Bold)
    $fill = [ordered]@{ properties = [ordered]@{
        show = (New-Literal 'true'); fillColor = (New-SolidColor $Color); transparency = (New-Literal '0D')
    }; selector = [ordered]@{ id = $State } }
    $text = [ordered]@{ properties = [ordered]@{
        show = (New-Literal 'true'); fontFamily = (New-Literal "'Microsoft YaHei'"); fontSize = (New-Literal '11D');
        bold = (New-Literal $(if ($Bold) { 'true' } else { 'false' })); fontColor = (New-SolidColor $TextColor);
        horizontalAlignment = (New-Literal "'center'"); verticalAlignment = (New-Literal "'middle'")
    }; selector = [ordered]@{ id = $State } }
    $outline = [ordered]@{ properties = [ordered]@{
        show = (New-Literal 'true'); lineColor = (New-SolidColor $colors.Border); weight = (New-Literal '1D'); transparency = (New-Literal '0D')
    }; selector = [ordered]@{ id = $State } }
    return [ordered]@{ Fill = $fill; Text = $text; Outline = $outline }
}

function Add-PageNavigator {
    param([string]$Page)
    $default = New-ButtonState 'default' $colors.Card $colors.Ink
    $hover = New-ButtonState 'hover' $colors.PaleBlue $colors.Blue -Bold
    $selected = New-ButtonState 'selected' $colors.Blue '#FFFFFF' -Bold
    $disabled = New-ButtonState 'disabled' '#EEF2F6' '#8A98A8'
    $staticFill = [ordered]@{ properties = $default.Fill.properties }
    $staticText = [ordered]@{ properties = $default.Text.properties }
    $staticOutline = [ordered]@{ properties = $default.Outline.properties }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position 500 14 620 44 40)
        visual = [ordered]@{
            visualType = 'pageNavigator'
            objects = [ordered]@{
                layout = @([ordered]@{ properties = [ordered]@{
                    orientation = (New-Literal "'0'"); rowCount = (New-Literal '1L'); columnCount = (New-Literal '4L'); cellPadding = (New-Literal '8L')
                } })
                pages = @([ordered]@{ properties = [ordered]@{
                    showHiddenPages = (New-Literal 'false'); showTooltipPages = (New-Literal 'false'); showByDefault = (New-Literal 'true')
                } })
                shape = @([ordered]@{ properties = [ordered]@{ tileShape = (New-Literal "'rectangleRounded'"); rectangleRoundedCurve = (New-Literal '8L') } })
                fill = @($staticFill, $default.Fill, $hover.Fill, $selected.Fill, $disabled.Fill)
                text = @($staticText, $default.Text, $hover.Text, $selected.Text, $disabled.Text)
                outline = @($staticOutline, $default.Outline, $hover.Outline, $selected.Outline, $disabled.Outline)
            }
            visualContainerObjects = [ordered]@{
                background = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                border = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
            }
        }
        howCreated = 'InsertVisualButton'
    }
    [void](Write-Visual $Page 'page-navigator' $visual)
}

function Add-NavigationButton {
    param(
        [string]$Page, [string]$Key, [string]$Label, [string]$TargetPage,
        [int]$X, [switch]$Active
    )
    $baseFill = if ($Active) { $colors.Blue } else { $colors.Card }
    $baseText = if ($Active) { '#FFFFFF' } else { $colors.Ink }
    $default = New-ButtonState 'default' $baseFill $baseText -Bold
    $hover = New-ButtonState 'hover' $(if ($Active) { $colors.Blue } else { $colors.PaleBlue }) $(if ($Active) { '#FFFFFF' } else { $colors.Blue }) -Bold
    $disabled = New-ButtonState 'disabled' '#EEF2F6' '#8A98A8'
    foreach ($state in @($default, $hover, $disabled)) {
        $state.Text.properties.text = (New-Literal "'$Label'")
    }
    $staticFill = [ordered]@{ properties = $default.Fill.properties }
    $staticText = [ordered]@{ properties = $default.Text.properties }
    $staticOutline = [ordered]@{ properties = $default.Outline.properties }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X 14 145 44 40)
        visual = [ordered]@{
            visualType = 'actionButton'
            objects = [ordered]@{
                shape = @([ordered]@{ properties = [ordered]@{ tileShape = (New-Literal "'rectangleRounded'"); rectangleRoundedCurve = (New-Literal '8L') } })
                fill = @($staticFill, $default.Fill, $hover.Fill, $disabled.Fill)
                text = @($staticText, $default.Text, $hover.Text, $disabled.Text)
                outline = @($staticOutline, $default.Outline, $hover.Outline, $disabled.Outline)
            }
            visualContainerObjects = [ordered]@{
                visualLink = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    type = (New-Literal "'PageNavigation'")
                    navigationSection = (New-Literal "'$TargetPage'")
                    enabledTooltip = (New-Literal "'前往$Label'")
                    showDefaultTooltip = (New-Literal 'false')
                } })
                background = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                border = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
            }
        }
        howCreated = 'InsertVisualButton'
    }
    [void](Write-Visual $Page $Key $visual)
}

function Add-ClearSlicersButton {
    param([string]$Page)
    $default = New-ButtonState 'default' $colors.Card $colors.Blue -Bold
    $hover = New-ButtonState 'hover' $colors.PaleBlue $colors.Blue -Bold
    $disabled = New-ButtonState 'disabled' '#EEF2F6' '#8A98A8'
    foreach ($state in @($default, $hover, $disabled)) {
        $state.Text.properties.text = (New-Literal "'清除筛选'")
    }
    $staticFill = [ordered]@{ properties = $default.Fill.properties }
    $staticText = [ordered]@{ properties = $default.Text.properties }
    $staticOutline = [ordered]@{ properties = $default.Outline.properties }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position 1232 70 184 76 320)
        visual = [ordered]@{
            visualType = 'actionButton'
            objects = [ordered]@{
                shape = @([ordered]@{ properties = [ordered]@{ tileShape = (New-Literal "'rectangleRounded'"); rectangleRoundedCurve = (New-Literal '8L') } })
                fill = @($staticFill, $default.Fill, $hover.Fill, $disabled.Fill)
                text = @($staticText, $default.Text, $hover.Text, $disabled.Text)
                outline = @($staticOutline, $default.Outline, $hover.Outline, $disabled.Outline)
            }
            visualContainerObjects = [ordered]@{
                visualLink = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true')
                    type = (New-Literal "'ClearAllSlicers'")
                    enabledTooltip = (New-Literal "'清除本页全部筛选并恢复默认视图'")
                    showDefaultTooltip = (New-Literal 'false')
                } })
                background = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                border = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                visualHeader = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
            }
        }
        howCreated = 'InsertVisualButton'
    }
    [void](Write-Visual $Page 'clear-slicers' $visual)
}

function Add-Chart {
    param(
        [string]$Page, [string]$Key,
        [ValidateSet('barChart', 'clusteredBarChart', 'clusteredColumnChart', 'columnChart', 'lineChart')][string]$Type,
        [string]$CategoryTable, [string]$CategoryColumn, [string]$CategoryLabel,
        [object[]]$MeasureSpecs, [string]$Title,
        [int]$X, [int]$Y, [int]$Width, [int]$Height,
        [ValidateSet('MeasureDescending', 'CategoryAscending')][string]$Sort = 'MeasureDescending',
        [int]$CategoryMargin = 35, [int]$Z = 400
    )
    $categoryProjection = New-ColumnProjection $CategoryTable $CategoryColumn $CategoryLabel -Active
    $measureProjections = @($MeasureSpecs | ForEach-Object { New-MeasureProjection $_.Name $_.Label })
    if ($Sort -eq 'CategoryAscending') {
        $sortField = $categoryProjection.field
        $direction = 'Ascending'
    }
    else {
        $sortField = $measureProjections[0].field
        $direction = 'Descending'
    }
    $dataPoint = @()
    foreach ($spec in $MeasureSpecs) {
        if ($spec.Color) {
            $dataPoint += [ordered]@{
                properties = [ordered]@{ fill = (New-SolidColor $spec.Color) }
                selector = [ordered]@{ metadata = "$measureTable.$($spec.Name)" }
            }
        }
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
                categoryAxis = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true'); fontFamily = (New-Literal "'Microsoft YaHei'"); fontSize = (New-Literal '9D');
                    labelColor = (New-SolidColor $colors.Muted); maxMarginFactor = (New-Literal "${CategoryMargin}L");
                    gridlineShow = (New-Literal 'false')
                } })
                valueAxis = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true'); fontFamily = (New-Literal "'Segoe UI'"); fontSize = (New-Literal '9D');
                    labelColor = (New-SolidColor $colors.Muted); gridlineShow = (New-Literal 'true');
                    gridlineColor = (New-SolidColor '#E9EEF4'); gridlineStyle = (New-Literal "'dotted'")
                } })
                labels = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                legend = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal $(if ($MeasureSpecs.Count -gt 1) { 'true' } else { 'false' }));
                    fontFamily = (New-Literal "'Microsoft YaHei'"); fontSize = (New-Literal '9D'); labelColor = (New-SolidColor $colors.Muted)
                } })
                dataPoint = $dataPoint
            }
            visualContainerObjects = (New-ContainerObjects $Title)
        }
    }
    [void](Write-Visual $Page $Key $visual)
}

function Add-ComboChart {
    param(
        [string]$Page, [string]$Key, [string]$CategoryTable, [string]$CategoryColumn,
        [string]$ColumnMeasure, [string]$LineMeasure, [string]$Title,
        [int]$X, [int]$Y, [int]$Width, [int]$Height, [int]$Z = 410
    )
    $categoryProjection = New-ColumnProjection $CategoryTable $CategoryColumn '月份' -Active
    $columnProjection = New-MeasureProjection $ColumnMeasure '广告花费（TWD）'
    $lineProjection = New-MeasureProjection $LineMeasure '归因收入（TWD）'
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = 'lineClusteredColumnComboChart'
            query = [ordered]@{
                queryState = [ordered]@{
                    Category = [ordered]@{ projections = @($categoryProjection) }
                    Y = [ordered]@{ projections = @($columnProjection) }
                    Y2 = [ordered]@{ projections = @($lineProjection) }
                }
                sortDefinition = [ordered]@{
                    sort = @([ordered]@{ field = $categoryProjection.field; direction = 'Ascending' })
                    isDefaultSort = $true
                }
            }
            objects = [ordered]@{
                categoryAxis = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true'); fontFamily = (New-Literal "'Segoe UI'"); fontSize = (New-Literal '9D');
                    labelColor = (New-SolidColor $colors.Muted); gridlineShow = (New-Literal 'false')
                } })
                valueAxis = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true'); showAxisTitle = (New-Literal 'true'); titleText = (New-Literal "'广告花费（TWD）'");
                    secShow = (New-Literal 'true'); secShowAxisTitle = (New-Literal 'true'); secTitleText = (New-Literal "'归因收入（TWD）'");
                    labelDisplayUnits = (New-Literal '1000000D'); secLabelDisplayUnits = (New-Literal '1000000D');
                    labelPrecision = (New-Literal '1L'); secLabelPrecision = (New-Literal '1L');
                    gridlineShow = (New-Literal 'true'); gridlineColor = (New-SolidColor '#E9EEF4'); gridlineStyle = (New-Literal "'dotted'")
                } })
                labels = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                legend = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'true'); fontSize = (New-Literal '9D'); labelColor = (New-SolidColor $colors.Muted) } })
                dataPoint = @([ordered]@{
                    properties = [ordered]@{ fill = (New-SolidColor $colors.Blue) }
                    selector = [ordered]@{ metadata = "$measureTable.$ColumnMeasure" }
                })
            }
            visualContainerObjects = (New-ContainerObjects $Title)
        }
    }
    [void](Write-Visual $Page $Key $visual)
}

function Add-ScatterChart {
    param(
        [string]$Page, [string]$Key,
        [string]$CategoryTable, [string]$CategoryColumn, [string]$SeriesTable, [string]$SeriesColumn,
        [string]$XMeasure, [string]$YMeasure, [string]$SizeMeasure, [object[]]$TooltipMeasures,
        [string]$Title, [string]$XAxisTitle, [string]$YAxisTitle,
        [int]$X, [int]$Y, [int]$Width, [int]$Height, [int]$Z = 420
    )
    $queryState = [ordered]@{
        Category = [ordered]@{ projections = @((New-ColumnProjection $CategoryTable $CategoryColumn '对象' -Active)) }
        Series = [ordered]@{ projections = @((New-ColumnProjection $SeriesTable $SeriesColumn '分组')) }
        X = [ordered]@{ projections = @((New-MeasureProjection $XMeasure $XAxisTitle)) }
        Y = [ordered]@{ projections = @((New-MeasureProjection $YMeasure $YAxisTitle)) }
        Size = [ordered]@{ projections = @((New-MeasureProjection $SizeMeasure '气泡大小')) }
    }
    if ($TooltipMeasures.Count -gt 0) {
        $queryState.Tooltips = [ordered]@{ projections = @($TooltipMeasures | ForEach-Object { New-MeasureProjection $_.Name $_.Label }) }
    }
    $visual = [ordered]@{
        '$schema' = $visualSchema
        name = ''
        position = (New-Position $X $Y $Width $Height $Z)
        visual = [ordered]@{
            visualType = 'scatterChart'
            query = [ordered]@{ queryState = $queryState }
            objects = [ordered]@{
                categoryAxis = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true'); showAxisTitle = (New-Literal 'true'); titleText = (New-Literal "'$XAxisTitle'");
                    fontFamily = (New-Literal "'Segoe UI'"); fontSize = (New-Literal '9D'); labelColor = (New-SolidColor $colors.Muted);
                    gridlineShow = (New-Literal 'true'); gridlineColor = (New-SolidColor '#E9EEF4'); gridlineStyle = (New-Literal "'dotted'")
                } })
                valueAxis = @([ordered]@{ properties = [ordered]@{
                    show = (New-Literal 'true'); showAxisTitle = (New-Literal 'true'); titleText = (New-Literal "'$YAxisTitle'");
                    fontFamily = (New-Literal "'Segoe UI'"); fontSize = (New-Literal '9D'); labelColor = (New-SolidColor $colors.Muted);
                    gridlineShow = (New-Literal 'true'); gridlineColor = (New-SolidColor '#E9EEF4'); gridlineStyle = (New-Literal "'dotted'")
                } })
                bubbles = @([ordered]@{ properties = [ordered]@{
                    bubbleSize = (New-Literal '45L'); markerRangeType = (New-Literal "'auto'"); preventOverflow = (New-Literal 'true'); markerShape = (New-Literal "'circle'")
                } })
                categoryLabels = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'false') } })
                legend = @([ordered]@{ properties = [ordered]@{ show = (New-Literal 'true'); fontSize = (New-Literal '9D'); labelColor = (New-SolidColor $colors.Muted) } })
            }
            visualContainerObjects = (New-ContainerObjects $Title)
        }
    }
    [void](Write-Visual $Page $Key $visual)
}

function Add-PageHeader {
    param([string]$Page, [string]$Title)
    Add-Textbox $Page 'page-title' $Title 24 8 452 52 '25px' $colors.Ink $colors.Page -Bold -Z 10
    Add-NavigationButton $Page 'nav-overview' '经营总览' '1e3893871908d0a9f051' 500 -Active:($Page -eq '1e3893871908d0a9f051')
    Add-NavigationButton $Page 'nav-product' '商品机会' '3a1b5d7e9f1029384756' 655 -Active:($Page -eq '3a1b5d7e9f1029384756')
    Add-NavigationButton $Page 'nav-customer' '用户价值' '4b2c6e8f0a1928374655' 810 -Active:($Page -eq '4b2c6e8f0a1928374655')
    Add-NavigationButton $Page 'nav-ads' '广告回报' '5c3d7f9a1b2837465019' 965 -Active:($Page -eq '5c3d7f9a1b2837465019')
    Add-Textbox $Page 'simulation-banner' '模拟数据 · TWD · FY2025' 1140 14 276 44 '13px' $colors.Ink $colors.PaleAmber -Bold -Align center -Z 20
    Add-Textbox $Page 'footer' '作品集模拟数据，仅用于展示分析方法，不代表真实 Shopee 或真实店铺表现。' 24 774 1392 30 '10px' $colors.Muted $colors.Page -Align center -Z 900
}

$additionalMeasures = @'

	/// Dynamic executive conclusion for the overview page; responds to report filters.
	measure 'Overview Insight Text' =
			VAR MonthTable = TOPN(1, ADDCOLUMNS(ALLSELECTED(calendar[month]), "__Sales", [Net Sales]), [__Sales], DESC, calendar[month], ASC)
			VAR TopMonth = MAXX(MonthTable, calendar[month])
			RETURN "本期净销售额 " & FORMAT([Net Sales] / 1000000, "0.00") & "M TWD，毛利 " & FORMAT([Gross Profit] / 1000000, "0.00") & "M TWD，毛利率 " & FORMAT([Gross Margin %], "0.0%") & "；" & TopMonth & " 为当前筛选下净销售额最高月份。"
		lineageTag: 0660ac10-5b7a-49f6-9a8f-47b273d17571

	measure 'Overview Invest Action' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(products[category]), "__Sales", [Net Sales]), [__Sales] > 0), [__Sales], DESC, products[category], ASC)
			RETURN "继续加码｜" & MAXX(T, products[category]) & "：净销售额 " & FORMAT(MAXX(T, [__Sales]) / 1000000, "0.00") & "M，第一。"
		lineageTag: b9b48711-e478-4de9-ac84-1b9e59e05257

	measure 'Overview Watch Action' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(products[category]), "__Margin", [Gross Margin %], "__Sales", [Net Sales]), [__Sales] > 0), [__Margin], ASC, products[category], ASC)
			RETURN "重点观察｜" & MAXX(T, products[category]) & "：毛利率 " & FORMAT(MAXX(T, [__Margin]), "0.0%") & "，最低。"
		lineageTag: 31776cd4-3434-4058-927a-bd332d5b3e5c

	measure 'Overview Optimize Action' =
			VAR Gap = [GMV] - [Net Sales]
			RETURN "优化处理｜销售额差额 " & FORMAT(Gap / 1000000, "0.00") & "M，复核退货。"
		lineageTag: 8210fc14-f753-429f-b0bf-dd70bc246696

	measure 'Product Insight Text' =
			VAR T = TOPN(1, ADDCOLUMNS(ALLSELECTED(products[product_name]), "__Opportunity", [Average Opportunity Score], "__Hot", [Average Hot Score]), [__Opportunity], DESC, [__Hot], DESC)
			RETURN MAXX(T, products[product_name]) & " 的机会分 " & FORMAT(MAXX(T, [__Opportunity]), "0.0") & "、热度分 " & FORMAT(MAXX(T, [__Hot]), "0.0") & "；当前筛选有 " & FORMAT([High Opportunity Products], "#,0") & " 个高机会商品。"
		lineageTag: 65a8a056-2ea6-42df-9019-f7ef54ec1c70

	measure 'Product Invest Action' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(products[product_name]), "__Opportunity", [Average Opportunity Score], "__Sales", [Net Sales]), [__Opportunity] >= 70), [__Opportunity], DESC, [__Sales], DESC)
			RETURN "值得加码｜" & MAXX(T, products[product_name]) & "：机会分 " & FORMAT(MAXX(T, [__Opportunity]), "0.0") & "，净销售额 " & FORMAT(MAXX(T, [__Sales]) / 1000, "#,0") & "K TWD。"
		lineageTag: 31ac6bc4-f82b-46c3-a374-66950c08eb41

	measure 'Product Optimize Action' =
			VAR Base = ADDCOLUMNS(ALLSELECTED(products[product_name]), "__Sales", [Net Sales], "__Margin", [Gross Margin %])
			VAR TopSales = TOPN(10, FILTER(Base, [__Sales] > 0), [__Sales], DESC)
			VAR T = TOPN(1, TopSales, [__Margin], ASC, [__Sales], DESC)
			RETURN "需要优化｜" & MAXX(T, products[product_name]) & "：Top 10 销售商品中毛利率最低，为 " & FORMAT(MAXX(T, [__Margin]), "0.0%") & "。"
		lineageTag: 2ad8e673-8961-4053-9434-daef8118bfd5

	measure 'Product Watch Action' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(products[product_name]), "__Hot", [Average Hot Score], "__Opportunity", [Average Opportunity Score]), [__Opportunity] < 70), [__Hot], DESC, [__Opportunity], DESC)
			RETURN "继续观察｜" & MAXX(T, products[product_name]) & "：热度分 " & FORMAT(MAXX(T, [__Hot]), "0.0") & "，但机会分 " & FORMAT(MAXX(T, [__Opportunity]), "0.0") & " 尚未达到 70。"
		lineageTag: 21e3d037-7f79-4abf-8e60-8c88c393ea5a

	measure 'Customer Insight Text' =
			VAR Champions = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "Champions")
			VAR ChampionSales = CALCULATE([Net Sales], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "Champions")
			VAR AtRisk = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "At Risk")
			RETURN "Champions 共 " & FORMAT(Champions, "#,0") & " 人，贡献净销售额 " & FORMAT(ChampionSales / 1000000, "0.00") & "M TWD；At Risk 共 " & FORMAT(AtRisk, "#,0") & " 人需要召回。"
		lineageTag: f538fa99-7c7e-498e-baa4-cb6f6b1f5ddf

	measure 'Customer Maintain Action' =
			VAR Champions = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "Champions")
			VAR Potential = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "Potential Loyalists")
			RETURN "价值经营｜Champions " & FORMAT(Champions, "#,0") & " 人：重点维护；Potential Loyalists " & FORMAT(Potential, "#,0") & " 人：促进复购。"
		lineageTag: 5ea552b6-687c-4c08-a584-99db8484f59a

	measure 'Customer Grow Action' =
			VAR NewPromising = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "New & Promising")
			VAR Loyal = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "Loyal")
			RETURN "成长经营｜New & Promising " & FORMAT(NewPromising, "#,0") & " 人：首购培育；Loyal " & FORMAT(Loyal, "#,0") & " 人：会员深化。"
		lineageTag: a141a4fe-b77f-4419-a5ad-8dc514bf1bbd

	measure 'Customer Recover Action' =
			VAR AtRisk = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "At Risk")
			VAR Hibernating = CALCULATE([Registered Users], REMOVEFILTERS(users[RFM Segment Display]), users[RFM Segment Display] = "Hibernating")
			RETURN "风险经营｜At Risk " & FORMAT(AtRisk, "#,0") & " 人：流失召回；Hibernating " & FORMAT(Hibernating, "#,0") & " 人：低成本唤醒。"
		lineageTag: 0d65f118-4d60-4848-a78f-d1a09d6477a2

	measure 'Ads Insight Text' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(ads[channel]), "__ROAS", [ROAS]), NOT ISBLANK([__ROAS])), [__ROAS], DESC, ads[channel], ASC)
			RETURN "每 1 TWD 广告费带来 " & FORMAT([ROAS], "0.00") & " TWD 归因收入；" & MAXX(T, ads[channel]) & " 的 ROAS 最高，为 " & FORMAT(MAXX(T, [__ROAS]), "0.00") & "x。"
		lineageTag: 378725cb-97c6-4489-91b2-eef6fe90032f

	measure 'Ads Increase Action' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(ads[channel]), "__ROAS", [ROAS], "__CPA", [CPA], "__Conversions", [Conversions]), NOT ISBLANK([__ROAS])), [__ROAS], DESC)
			RETURN "建议增加预算｜" & MAXX(T, ads[channel]) & "：ROAS " & FORMAT(MAXX(T, [__ROAS]), "0.00") & "x，CPA " & FORMAT(MAXX(T, [__CPA]), "#,0") & " TWD，转化 " & FORMAT(MAXX(T, [__Conversions]), "#,0") & "。"
		lineageTag: 675227f0-73db-4a93-b5bf-7bb83a26bf7c

	measure 'Ads Watch Action' =
			VAR Base = ADDCOLUMNS(ALLSELECTED(ads[channel]), "__ROAS", [ROAS], "__CPA", [CPA])
			VAR Ranked = ADDCOLUMNS(Base, "__Rank", RANKX(Base, [__ROAS],, DESC, DENSE))
			VAR T = TOPN(1, FILTER(Ranked, [__Rank] = 2), [__ROAS], DESC)
			RETURN "建议观察｜" & MAXX(T, ads[channel]) & "：ROAS " & FORMAT(MAXX(T, [__ROAS]), "0.00") & "x，CPA " & FORMAT(MAXX(T, [__CPA]), "#,0") & " TWD；继续验证增量效果。"
		lineageTag: b6d953da-7f1f-4684-b73e-b0ddb2c97fc3

	measure 'Ads Reduce Action' =
			VAR T = TOPN(1, FILTER(ADDCOLUMNS(ALLSELECTED(ads[channel]), "__ROAS", [ROAS], "__CPA", [CPA]), NOT ISBLANK([__ROAS])), [__ROAS], ASC, ads[channel], ASC)
			RETURN "建议减少预算｜" & MAXX(T, ads[channel]) & "：ROAS " & FORMAT(MAXX(T, [__ROAS]), "0.00") & "x，CPA " & FORMAT(MAXX(T, [__CPA]), "#,0") & " TWD，为当前筛选效率最低。"
		lineageTag: 4b434534-2f25-47b2-b1c1-4456385e9446
'@

$measurePath = Join-Path $modelRoot 'definition\tables\KPI Measures.tmdl'
$measureText = [System.IO.File]::ReadAllText($measurePath)
if (-not $measureText.Contains("measure 'Overview Insight Text'")) {
    $marker = "`tcolumn Dummy"
    $markerIndex = $measureText.IndexOf($marker, [StringComparison]::Ordinal)
    if ($markerIndex -lt 0) { throw 'Could not locate the calculated-table Dummy column in KPI Measures.tmdl.' }
    $measureText = $measureText.Insert($markerIndex, $additionalMeasures + [Environment]::NewLine)
    [System.IO.File]::WriteAllText($measurePath, $measureText, [System.Text.UTF8Encoding]::new($false))
}

# Keep concise action copy even when the storytelling measures already exist from an earlier V1.2 generation.
$measureText = [System.IO.File]::ReadAllText($measurePath)
$measureText = $measureText.Replace('M TWD，当前筛选贡献第一。', 'M，贡献第一。')
$measureText = $measureText.Replace('，当前筛选品类中最低。', '，品类最低。')
$measureText = $measureText.Replace('M TWD；复核退款与折扣结构。', 'M；复核退货。')
$measureText = $measureText.Replace('M，贡献第一。', 'M，第一。')
$measureText = $measureText.Replace('，品类最低。', '，最低。')
$measureText = $measureText.Replace('GMV 与净销售额差额 ', '销售额差额 ')
$measureText = $measureText.Replace('M；复核退货。', 'M，复核退货。')
[System.IO.File]::WriteAllText($measurePath, $measureText, [System.Text.UTF8Encoding]::new($false))

$kpiDisplayMeasures = @'

	/// Compact display-only currency strings used by executive cards; base measures and calculation logic are unchanged.
	measure 'GMV KPI Text' = FORMAT([GMV] / 1000000, "0.00") & "M TWD"
		lineageTag: 143d7520-04a8-43a3-942c-fd51f094524f

	measure 'Net Sales KPI Text' = FORMAT([Net Sales] / 1000000, "0.00") & "M TWD"
		lineageTag: 418aebac-e35c-4a15-8dfe-0374c7d47404

	measure 'Gross Profit KPI Text' = FORMAT([Gross Profit] / 1000000, "0.00") & "M TWD"
		lineageTag: 52865556-58d1-4e93-ae63-aa17b73c6965

	measure 'Ad Spend KPI Text' = FORMAT([Ad Spend] / 1000000, "0.00") & "M TWD"
		lineageTag: 95c26103-1034-46a5-bbdf-0d4efaa88b71

	measure 'Attributed Revenue KPI Text' = FORMAT([Attributed Revenue] / 1000000, "0.00") & "M TWD"
		lineageTag: ebd3653c-129d-4eae-a5ee-2425c4768463
'@

$measureText = [System.IO.File]::ReadAllText($measurePath)
if (-not $measureText.Contains("measure 'GMV KPI Text'")) {
    $marker = "`tcolumn Dummy"
    $markerIndex = $measureText.IndexOf($marker, [StringComparison]::Ordinal)
    if ($markerIndex -lt 0) { throw 'Could not locate the calculated-table Dummy column for KPI display measures.' }
    $measureText = $measureText.Insert($markerIndex, $kpiDisplayMeasures + [Environment]::NewLine)
    [System.IO.File]::WriteAllText($measurePath, $measureText, [System.Text.UTF8Encoding]::new($false))
}

$usersPath = Join-Path $modelRoot 'definition\tables\users.tmdl'
$usersText = [System.IO.File]::ReadAllText($usersPath)
if (-not $usersText.Contains("column 'RFM Segment Display'")) {
    $newColumns = @'
	/// RFM label used by report visuals. Users without a completed purchase are identified explicitly instead of appearing as a blank segment.
	column 'RFM Segment Display'
		dataType: string
		lineageTag: 0b97cda3-e7e9-4496-a414-bb6308f79c86
		summarizeBy: none
		sourceColumn: RFM Segment Display

	column 'RFM Business Action'
		dataType: string
		lineageTag: 67fc19e8-708f-4fe8-b7de-9ac78732ba24
		summarizeBy: none
		sourceColumn: RFM Business Action

'@
    $columnMarker = "`tcolumn customer_type"
    $columnIndex = $usersText.IndexOf($columnMarker, [StringComparison]::Ordinal)
    if ($columnIndex -lt 0) { throw 'Could not locate customer_type in users.tmdl.' }
    $usersText = $usersText.Insert($columnIndex, $newColumns)
    $oldStep = '#"Added Customer Type" = Table.AddColumn(#"Changed Type", "customer_type", each if [frequency] = null then "No Purchase" else if [frequency] >= 2 then "Repeat" else "New", type text)'
    $newSteps = @'
#"Added Customer Type" = Table.AddColumn(#"Changed Type", "customer_type", each if [frequency] = null then "No Purchase" else if [frequency] >= 2 then "Repeat" else "New", type text),
				    #"Added RFM Segment Display" = Table.AddColumn(#"Added Customer Type", "RFM Segment Display", each if [rfm_segment] = null or Text.Trim([rfm_segment]) = "" then "未购买 / 未分群" else [rfm_segment], type text),
				    #"Added RFM Business Action" = Table.AddColumn(#"Added RFM Segment Display", "RFM Business Action", each if [RFM Segment Display] = "Champions" then "重点维护" else if [RFM Segment Display] = "Potential Loyalists" then "促进复购" else if [RFM Segment Display] = "New & Promising" then "首购培育" else if [RFM Segment Display] = "At Risk" then "流失召回" else if [RFM Segment Display] = "Hibernating" then "低成本唤醒" else if [RFM Segment Display] = "Loyal" then "会员深化" else "未购买用户培育", type text)
'@
    if (-not $usersText.Contains($oldStep)) { throw 'Could not locate the users Customer Type Power Query step.' }
    $usersText = $usersText.Replace($oldStep, $newSteps.TrimEnd("`r", "`n"))
    $usersText = $usersText.Replace('in' + [Environment]::NewLine + "`t`t`t`t    #`"Added Customer Type`"", 'in' + [Environment]::NewLine + "`t`t`t`t    #`"Added RFM Business Action`"")
    [System.IO.File]::WriteAllText($usersPath, $usersText, [System.Text.UTF8Encoding]::new($false))
}

# Normalize currency formats and keep every PBIP import portable.
Get-ChildItem -LiteralPath (Join-Path $modelRoot 'definition\tables') -Filter '*.tmdl' | ForEach-Object {
    $tmdl = [System.IO.File]::ReadAllText($_.FullName)
    $normalized = $tmdl.Replace('NT$ #,0.00', '#,0.00 "TWD"').Replace('NT$ #,0', '#,0 "TWD"')
    if ($normalized -ne $tmdl) {
        [System.IO.File]::WriteAllText($_.FullName, $normalized, [System.Text.UTF8Encoding]::new($false))
    }
}

$dataRootExpressionTemplate = @'
expression DataRoot = "__DATA_ROOT__" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
	lineageTag: 31da920a-496c-46e2-8d20-f365f8bd9184
	annotation PBI_NavigationStepName = Navigation
	annotation PBI_ResultType = Text
'@
$dataRootExpression = $dataRootExpressionTemplate.Replace('__DATA_ROOT__', $BuildDataRoot)
$expressionPath = Join-Path $modelRoot 'definition\expressions.tmdl'
[System.IO.File]::WriteAllText($expressionPath, $dataRootExpression + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

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

Get-ChildItem -LiteralPath (Join-Path $modelRoot 'definition') -Filter '*.tmdl' -File -Recurse | ForEach-Object {
    $tmdl = [System.IO.File]::ReadAllText($_.FullName)
    $normalized = $tmdl.TrimEnd("`r", "`n") + [Environment]::NewLine
    if ($normalized -ne $tmdl) {
        [System.IO.File]::WriteAllText($_.FullName, $normalized, [System.Text.UTF8Encoding]::new($false))
    }
}

[void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $themeTarget))
[System.IO.File]::Copy($themeSource, $themeTarget, $true)

$definitionPbir = [ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json'
    version = '4.0'
    datasetReference = [ordered]@{ byPath = [ordered]@{ path = '../Ecommerce-Operations-Analytics-Assistant.SemanticModel' } }
}
Write-JsonFile (Join-Path $reportRoot 'definition.pbir') $definitionPbir

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
            name = 'SharedResources'; type = 'SharedResources';
            items = @([ordered]@{ name = 'Fluent2-CY26SU08'; path = 'BaseThemes/Fluent2-CY26SU08.json'; type = 'BaseTheme' })
        },
        [ordered]@{
            name = 'RegisteredResources'; type = 'RegisteredResources';
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

$overviewPage = '1e3893871908d0a9f051'
$productPage = '3a1b5d7e9f1029384756'
$customerPage = '4b2c6e8f0a1928374655'
$adsPage = '5c3d7f9a1b2837465019'

New-Page $overviewPage '经营总览'
Add-PageHeader $overviewPage '经营总览'
Add-Slicer $overviewPage 'date' 'calendar' 'date' '日期范围' 24 70 286 76 -Mode Between -SyncGroup 'DateSync'
Add-Slicer $overviewPage 'category' 'products' 'category' '品类' 326 70 286 76 -SyncGroup 'CategorySync'
Add-Slicer $overviewPage 'region' 'users' 'region' '地区' 628 70 286 76 -SyncGroup 'RegionSync'
Add-Slicer $overviewPage 'channel' 'users' 'acquisition_channel' '获客渠道' 930 70 286 76
Add-ClearSlicersButton $overviewPage
Add-DynamicTextCard $overviewPage 'business-conclusion' 'Overview Insight Text' 24 158 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $overviewPage 'kpi-net-sales' 'Net Sales KPI Text' '净销售额' 24 228 336 88 $colors.Blue 0 0
Add-KpiCard $overviewPage 'kpi-gross-profit' 'Gross Profit KPI Text' '毛利' 376 228 336 88 $colors.Teal 0 0
Add-KpiCard $overviewPage 'kpi-margin' 'Gross Margin %' '毛利率' 728 228 336 88 $colors.Teal 0 1
Add-KpiCard $overviewPage 'kpi-roas' 'ROAS' '广告回报 ROAS' 1080 228 336 88 $colors.Blue 0 2
Add-KpiCard $overviewPage 'secondary-gmv' 'GMV KPI Text' 'GMV' 24 322 266 70 $colors.Muted 0 0 -FontSize 18
Add-KpiCard $overviewPage 'secondary-orders' 'Completed Orders' '有效订单量' 306 322 266 70 $colors.Muted 0 0 -FontSize 18
Add-KpiCard $overviewPage 'secondary-aov' 'AOV' '客单价 AOV' 588 322 264 70 $colors.Muted 0 0 -FontSize 18
Add-KpiCard $overviewPage 'secondary-users' 'Purchasing Users' '购买用户数' 868 322 266 70 $colors.Muted 0 0 -FontSize 18
Add-KpiCard $overviewPage 'secondary-repeat' 'Repeat Rate FY2025 %' '复购率' 1150 322 266 70 $colors.Muted 0 1 -FontSize 18
Add-Chart $overviewPage 'monthly-trend' 'lineChart' 'calendar' 'month' '月份' @(
    @{ Name = 'GMV'; Label = 'GMV'; Color = $colors.Blue },
    @{ Name = 'Net Sales'; Label = '净销售额'; Color = $colors.Teal }
) '1–12 月 GMV 与净销售额趋势（TWD）' 24 404 842 206 -Sort CategoryAscending -CategoryMargin 18
Add-Chart $overviewPage 'category-contribution' 'clusteredBarChart' 'products' 'category' '品类' @(
    @{ Name = 'Net Sales'; Label = '净销售额'; Color = $colors.Blue },
    @{ Name = 'Gross Profit'; Label = '毛利'; Color = $colors.Teal }
) '品类净销售额与毛利贡献（按净销售额降序）' 882 404 534 206 -CategoryMargin 36
Add-DynamicTextCard $overviewPage 'action-invest' 'Overview Invest Action' 24 648 453 110 $colors.PaleTeal $colors.Ink 9
Add-DynamicTextCard $overviewPage 'action-watch' 'Overview Watch Action' 493 648 453 110 $colors.PaleAmber $colors.Ink 9
Add-DynamicTextCard $overviewPage 'action-optimize' 'Overview Optimize Action' 962 648 454 110 $colors.PaleRed $colors.Ink 9
Add-Textbox $overviewPage 'action-heading' '下一步行动' 24 612 1392 33 '13px' $colors.Ink $colors.Page -Bold -Z 500

New-Page $productPage '商品机会'
Add-PageHeader $productPage '商品机会'
Add-Slicer $productPage 'category' 'products' 'category' '品类' 24 70 286 76 -SyncGroup 'CategorySync'
Add-Slicer $productPage 'price-band' 'products' 'price_band' '价格带' 326 70 286 76
Add-Textbox $productPage 'matrix-note' '现有数据无独立竞争度字段；矩阵采用机会分 × 热度分，不伪造竞争指标。' 628 70 588 76 '11px' $colors.Muted $colors.Card -Z 310
Add-ClearSlicersButton $productPage
Add-DynamicTextCard $productPage 'business-conclusion' 'Product Insight Text' 24 158 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $productPage 'kpi-product-count' 'Product Count' '商品数量' 24 228 266 82 $colors.Blue 0 0
Add-KpiCard $productPage 'kpi-opportunity-count' 'High Opportunity Products' '高机会商品数量' 306 228 266 82 $colors.Amber 0 0
Add-KpiCard $productPage 'kpi-units' 'Units Sold' '有效销量' 588 228 264 82 $colors.Blue 0 0
Add-KpiCard $productPage 'kpi-net-sales' 'Net Sales KPI Text' '净销售额' 868 228 266 82 $colors.Blue 0 0
Add-KpiCard $productPage 'kpi-profit' 'Gross Profit KPI Text' '毛利' 1150 228 266 82 $colors.Teal 0 0
Add-ScatterChart $productPage 'opportunity-matrix' 'products' 'product_name' 'products' 'category' 'Average Opportunity Score' 'Average Hot Score' 'Net Sales' @(
    @{ Name = 'Units Sold'; Label = '有效销量' },
    @{ Name = 'Gross Profit'; Label = '毛利（TWD）' }
) '商品机会矩阵：机会分 × 热度分（气泡=净销售额，颜色=品类）' '机会分' '热度分' 24 322 610 288
Add-Chart $productPage 'product-ranking' 'clusteredBarChart' 'products' 'product_name' '商品名称' @(
    @{ Name = 'Top 10 Product Net Sales'; Label = '净销售额'; Color = $colors.Blue },
    @{ Name = 'Top 10 Product Gross Profit'; Label = '毛利'; Color = $colors.Teal }
) '商品 Top 10：净销售额与毛利（TWD）' 650 322 766 288 -CategoryMargin 52
Add-Chart $productPage 'price-band' 'clusteredColumnChart' 'products' 'price_band' '价格带' @(
    @{ Name = 'Net Sales'; Label = '净销售额'; Color = $colors.Blue },
    @{ Name = 'Gross Profit'; Label = '毛利'; Color = $colors.Teal }
) '价格带：净销售额与毛利（TWD）' 24 622 452 136 -Sort CategoryAscending -CategoryMargin 22
Add-DynamicTextCard $productPage 'action-invest' 'Product Invest Action' 492 622 292 136 $colors.PaleTeal $colors.Ink 11
Add-DynamicTextCard $productPage 'action-optimize' 'Product Optimize Action' 800 622 292 136 $colors.PaleRed $colors.Ink 11
Add-DynamicTextCard $productPage 'action-watch' 'Product Watch Action' 1108 622 308 136 $colors.PaleAmber $colors.Ink 11

New-Page $customerPage '用户价值'
Add-PageHeader $customerPage '用户价值'
Add-Slicer $customerPage 'region' 'users' 'region' '地区' 24 70 260 76 -SyncGroup 'RegionSync'
Add-Slicer $customerPage 'segment' 'users' 'RFM Segment Display' 'RFM 客群' 300 70 320 76
Add-Slicer $customerPage 'customer-type' 'users' 'customer_type' '新老用户' 636 70 260 76
Add-Textbox $customerPage 'rfm-note' 'RFM 观察日：2026-01-01；空白来源为无 completed 购买行为，现显式标为“未购买 / 未分群”。' 912 70 304 76 '10px' $colors.Muted $colors.Card -Z 310
Add-ClearSlicersButton $customerPage
Add-DynamicTextCard $customerPage 'business-conclusion' 'Customer Insight Text' 24 158 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $customerPage 'kpi-users' 'Purchasing Users' '购买用户数' 24 228 266 82 $colors.Blue 0 0
Add-KpiCard $customerPage 'kpi-repeat' 'Repeat Rate FY2025 %' '复购率' 306 228 266 82 $colors.Teal 0 1
Add-KpiCard $customerPage 'kpi-recency' 'Average Recency' '平均 Recency（天）' 588 228 264 82 $colors.Amber 0 0
Add-KpiCard $customerPage 'kpi-frequency' 'Average Frequency' '平均 Frequency' 868 228 266 82 $colors.Blue 0 1
Add-KpiCard $customerPage 'kpi-monetary' 'Average Monetary' '平均 Monetary' 1150 228 266 82 $colors.Teal 0 0
Add-Chart $customerPage 'segment-size' 'clusteredBarChart' 'users' 'RFM Segment Display' 'RFM 客群' @(
    @{ Name = 'Registered Users'; Label = '客群人数'; Color = $colors.Blue }
) '客群规模（含显式未购买 / 未分群）' 24 322 590 284 -CategoryMargin 45
Add-Chart $customerPage 'segment-value' 'clusteredBarChart' 'users' 'RFM Segment Display' 'RFM 客群' @(
    @{ Name = 'Net Sales'; Label = '净销售额'; Color = $colors.Teal }
) '客群价值：净销售额贡献（TWD）' 630 322 500 284 -CategoryMargin 45
Add-Chart $customerPage 'region-distribution' 'clusteredColumnChart' 'users' 'region' '地区' @(
    @{ Name = 'Registered Users'; Label = '注册用户数'; Color = $colors.Blue }
) '地区分布（辅助）' 1146 322 270 284 -CategoryMargin 20
Add-DynamicTextCard $customerPage 'action-maintain' 'Customer Maintain Action' 24 622 453 136 $colors.PaleTeal $colors.Ink 11
Add-DynamicTextCard $customerPage 'action-grow' 'Customer Grow Action' 493 622 453 136 $colors.PaleBlue $colors.Ink 11
Add-DynamicTextCard $customerPage 'action-recover' 'Customer Recover Action' 962 622 454 136 $colors.PaleRed $colors.Ink 11

New-Page $adsPage '广告回报'
Add-PageHeader $adsPage '广告回报'
Add-Slicer $adsPage 'date' 'calendar' 'date' '日期范围' 24 70 300 76 -Mode Between -SyncGroup 'DateSync'
Add-Slicer $adsPage 'channel' 'ads' 'channel' '广告渠道' 340 70 280 76
Add-Slicer $adsPage 'campaign' 'ads' 'campaign_name' '广告活动' 636 70 420 76
Add-Textbox $adsPage 'attribution-note' '归因收入 ≠ 订单净销售额；金额均为 TWD。' 1072 70 144 76 '9px' $colors.Muted $colors.Card -Z 310
Add-ClearSlicersButton $adsPage
Add-DynamicTextCard $adsPage 'business-conclusion' 'Ads Insight Text' 24 158 1392 58 $colors.PaleBlue $colors.Ink 17
Add-KpiCard $adsPage 'kpi-spend' 'Ad Spend KPI Text' '广告花费' 24 228 222 82 $colors.Blue 0 0 -FontSize 20
Add-KpiCard $adsPage 'kpi-revenue' 'Attributed Revenue KPI Text' '归因收入' 258 228 222 82 $colors.Teal 0 0 -FontSize 20
Add-KpiCard $adsPage 'kpi-roas' 'ROAS' 'ROAS' 492 228 222 82 $colors.Teal 0 2
Add-KpiCard $adsPage 'kpi-cpa' 'CPA' 'CPA' 726 228 222 82 $colors.Red 0 2
Add-KpiCard $adsPage 'kpi-ctr' 'CTR %' 'CTR' 960 228 222 82 $colors.Blue 0 2
Add-KpiCard $adsPage 'kpi-cvr' 'CVR %' 'CVR' 1194 228 222 82 $colors.Blue 0 2
Add-ComboChart $adsPage 'ad-trend' 'calendar' 'month' 'Ad Spend' 'Attributed Revenue' '月度广告花费（柱）与归因收入（线）— 独立双轴' 24 322 650 284
Add-ScatterChart $adsPage 'campaign-efficiency' 'ads' 'campaign_name' 'ads' 'channel' 'Ad Spend' 'ROAS' 'Conversions' @(
    @{ Name = 'Attributed Revenue'; Label = '归因收入（TWD）' },
    @{ Name = 'CPA'; Label = 'CPA（TWD）' },
    @{ Name = 'CTR %'; Label = 'CTR' },
    @{ Name = 'CVR %'; Label = 'CVR' }
) '活动效率：花费 × ROAS（气泡=转化量，颜色=渠道）' '广告花费（TWD）' 'ROAS（x）' 690 322 726 284
Add-DynamicTextCard $adsPage 'action-increase' 'Ads Increase Action' 24 622 453 136 $colors.PaleTeal $colors.Ink 11
Add-DynamicTextCard $adsPage 'action-watch' 'Ads Watch Action' 493 622 453 136 $colors.PaleAmber $colors.Ink 11
Add-DynamicTextCard $adsPage 'action-reduce' 'Ads Reduce Action' 962 622 454 136 $colors.PaleRed $colors.Ink 11

$pagesMetadata = [ordered]@{
    '$schema' = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json'
    pageOrder = @($overviewPage, $productPage, $customerPage, $adsPage)
    activePageName = $overviewPage
}
Write-JsonFile (Join-Path $pagesRoot 'pages.json') $pagesMetadata

Write-Host 'PBIR V1.2 report generated: 4 executive-storytelling pages.'
Write-Host 'Pages: 经营总览, 商品机会, 用户价值, 广告回报.'
Write-Host 'Original 37 measures preserved; 21 display-only storytelling/KPI measures added.'
