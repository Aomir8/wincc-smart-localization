param(
    [Parameter(Mandatory=$true)][ValidateSet('Snapshot','Query')][string]$Action,
    [Parameter(Mandatory=$true)][string]$Project,
    [string]$Destination,
    [string]$SqlFile,
    [string]$ResultFile,
    [string]$LocalDbExe,
    [string]$LocalDbVersion,
    [string]$Culture
)

$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath $Project).ProviderPath
$folder = [IO.Path]::GetDirectoryName($projectPath)
$stem = [IO.Path]::GetFileNameWithoutExtension($projectPath)
$logPath = Join-Path $folder ($stem + '_log.ldfsmart')
if (-not [IO.File]::Exists($logPath)) { throw "Missing paired log: $logPath" }

if ($Action -eq 'Snapshot') {
    if ($Culture -and $Culture -notin [Globalization.CultureInfo]::GetCultures('SpecificCultures').Name) {
        throw "Windows does not recognize the target as a specific project culture: $Culture"
    }
    $streams = @{}
    try {
        foreach ($path in @($projectPath, $logPath)) {
            $streams[$path] = [IO.File]::Open($path, 'Open', 'Read', 'Read')
        }
        $rootStem = $stem -replace '(?i)(\.backup)+$', ''
        foreach ($file in Get-ChildItem -LiteralPath $folder -File -Filter '*.data') {
            if ($file.BaseName.StartsWith($stem + '_', [StringComparison]::OrdinalIgnoreCase) -or
                $file.BaseName.StartsWith($rootStem + '_', [StringComparison]::OrdinalIgnoreCase) -or
                $file.BaseName -eq $stem) {
                $streams[$file.FullName] = [IO.File]::Open($file.FullName, 'Open', 'Read', 'Read')
            }
        }
        foreach ($path in $streams.Keys) {
            $output = Join-Path $Destination ([IO.Path]::GetFileName($path))
            $outputStream = [IO.File]::Open($output, 'CreateNew', 'Write', 'None')
            try { $streams[$path].CopyTo($outputStream) }
            finally { $outputStream.Dispose() }
        }
    } finally {
        foreach ($stream in $streams.Values) { $stream.Dispose() }
    }
    return
}

if (-not $LocalDbExe) {
    $installed = Get-Command SqlLocalDB.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($installed) { $LocalDbExe = $installed.Source }
    else {
        $sqlRoot = Join-Path $env:ProgramFiles 'Microsoft SQL Server'
        $LocalDbExe = Get-ChildItem -LiteralPath $sqlRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+$' } |
            Sort-Object { [int]$_.Name } -Descending |
            ForEach-Object { Join-Path $_.FullName 'Tools\Binn\SqlLocalDB.exe' } |
            Where-Object { [IO.File]::Exists($_) } | Select-Object -First 1
    }
}
if (-not $LocalDbExe -or -not [IO.File]::Exists($LocalDbExe)) {
    throw 'SQL Server Express LocalDB was not found. Supply the installed WinCC-compatible SqlLocalDB.exe.'
}

$instance = 'HmiLocalization_' + [guid]::NewGuid().ToString('N').Substring(0, 12)
$database = 'HmiLocalizationCopy'
$created = $false
$attached = $false
$connection = $null
$command = $null
$sqlProject = $projectPath.Replace("'", "''")
$sqlLog = $logPath.Replace("'", "''")
$sql = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $SqlFile).ProviderPath)

try {
    $createArgs = @('create', $instance)
    if ($LocalDbVersion) { $createArgs += $LocalDbVersion }
    $creation = & $LocalDbExe @createArgs
    if ($LASTEXITCODE -ne 0) { throw "Cannot create LocalDB instance: $creation" }
    $created = $true
    $startup = & $LocalDbExe start $instance
    if ($LASTEXITCODE -ne 0) { throw "Cannot start LocalDB instance: $startup" }

    $connection = New-Object System.Data.SqlClient.SqlConnection "Server=(localdb)\$instance;Integrated Security=true;Pooling=false;Connection Timeout=30"
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandTimeout = 180

    $command.CommandText = "DBCC CHECKPRIMARYFILE (N'$sqlProject', 2) WITH NO_INFOMSGS"
    $header = $command.ExecuteReader()
    $originalVersion = $null
    try {
        while ($header.Read()) {
            if ($header.GetString(0) -eq 'Database version') { $originalVersion = [int]$header.GetValue(1) }
        }
    } finally { $header.Dispose() }
    if ($null -eq $originalVersion) { throw 'Cannot read the database format version.' }

    $command.CommandText = "CREATE DATABASE [$database] ON (FILENAME=N'$sqlProject'), (FILENAME=N'$sqlLog') FOR ATTACH"
    $null = $command.ExecuteNonQuery()
    $attached = $true
    $connection.ChangeDatabase($database)

    $command.CommandText = "SELECT CONVERT(int, DATABASEPROPERTYEX(DB_NAME(), 'Version'))"
    $attachedVersion = [int]$command.ExecuteScalar()
    if ($originalVersion -ne $attachedVersion) {
        throw "LocalDB upgraded this temporary copy from database format $originalVersion to $attachedVersion. Rerun with the matching LocalDB version."
    }

    $command.CommandText = $sql
    $results = New-Object 'System.Collections.Generic.List[object]'
    $reader = $command.ExecuteReader()
    try {
        do {
            if ($reader.FieldCount -eq 0) { continue }
            $rows = New-Object 'System.Collections.Generic.List[object]'
            while ($reader.Read()) {
                $row = [ordered]@{}
                for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                    $value = $reader.GetValue($i)
                    if ($value -is [DBNull]) { $value = $null }
                    elseif ($value -is [byte[]]) { $value = [Convert]::ToBase64String($value) }
                    $row[$reader.GetName($i)] = $value
                }
                $rows.Add($row)
            }
            $results.Add($rows.ToArray())
        } while ($reader.NextResult())
    } finally { $reader.Dispose() }

    $connection.ChangeDatabase('master')
    $command.CommandText = "EXEC sp_detach_db @dbname=N'$database'"
    $null = $command.ExecuteNonQuery()
    $attached = $false
    $data = @{ database_version = $originalVersion; results = $results.ToArray() }
    [IO.File]::WriteAllText($ResultFile, (ConvertTo-Json -InputObject $data -Depth 12), [Text.UTF8Encoding]::new($false))
} finally {
    try {
        if ($attached -and $connection -and $connection.State -eq 'Open') {
            $connection.ChangeDatabase('master')
            $command.CommandText = "EXEC sp_detach_db @dbname=N'$database'"
            $null = $command.ExecuteNonQuery()
        }
    } finally {
        if ($connection) { $connection.Dispose() }
        if ($created) {
            $null = & $LocalDbExe stop $instance
            $null = & $LocalDbExe delete $instance
        }
    }
}
