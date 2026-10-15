param([string]$Destination = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ToolsEnabled\Head Gasket Bench\0.1.4'))
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
if ($Destination -notmatch '^[A-Za-z]:\\' -or $Destination.StartsWith('\\') -or $Destination.Substring(2).Contains(':')) { throw 'Choose a fully qualified local drive path without alternate streams.' }
$Destination = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $Destination) { throw 'Destination already exists. Choose a new folder; nothing has been changed.' }
for ($parent = [IO.Directory]::GetParent($Destination); $parent; $parent = $parent.Parent) {
  if ($parent.Exists -and ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse-point install ancestors are refused.' }
  if ($parent.Exists) {
    $parentAcl = Get-Acl -LiteralPath $parent.FullName
    $rawAcl = New-Object Security.AccessControl.RawSecurityDescriptor($parentAcl.GetSecurityDescriptorBinaryForm(), 0)
    if ($null -eq $rawAcl.DiscretionaryAcl) { throw 'An install ancestor has a null DACL.' }
    foreach ($ace in $rawAcl.DiscretionaryAcl) {
      if ([int]$ace.AceType -notin @(0,1)) { throw 'An install ancestor has an unrecognized ACL entry.' }
    }
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $trusted = @($currentSid,'S-1-5-18','S-1-5-32-544')
    if ($trusted -notcontains $parentAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value) { throw 'An install ancestor belongs to an untrusted account.' }
    foreach ($rule in $parentAcl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
      if ($rule.AccessControlType -eq 'Allow' -and $rule.PropagationFlags -notlike '*InheritOnly*' -and $trusted -notcontains $rule.IdentityReference.Value -and ([long]$rule.FileSystemRights -band 0x500D0140)) { throw 'Another account can replace an install ancestor; choose a private destination.' }
    }
  }
}
$manifest = Get-Content -LiteralPath (Join-Path $source 'WINDOWS-MANIFEST.json') -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'headgasket/windows-payload/v1') { throw 'Unrecognized payload manifest.' }
$expected = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($item in $manifest.files) {
  if ($item.path -match '(^|[/\\])\.\.([/\\]|$)|:|^[/\\]' -or -not $expected.Add($item.path)) { throw 'Unsafe/duplicate manifest path.' }
  $file = Join-Path $source $item.path
  $info = Get-Item -LiteralPath $file
  if ($info.PSIsContainer -or ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $info.Length -ne $item.bytes -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw ('Payload verification failed: ' + $item.path) }
}
foreach ($file in Get-ChildItem -LiteralPath $source -Force -Recurse) {
  if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse payload refused.' }
  if (-not $file.PSIsContainer) {
    $relative = $file.FullName.Substring($source.Length + 1).Replace('\','/')
    if ($relative -ne 'WINDOWS-MANIFEST.json' -and -not $expected.Contains($relative)) { throw ('Unlisted payload file: ' + $relative) }
  }
}
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetOwner($sid)
$acl.SetAccessRuleProtection($true, $false)
foreach ($who in @($sid.Value,'S-1-5-18','S-1-5-32-544')) {
  $rule = New-Object Security.AccessControl.FileSystemAccessRule ((New-Object Security.Principal.SecurityIdentifier($who)), 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
  $acl.AddAccessRule($rule)
}
$missing = New-Object 'System.Collections.Generic.List[string]'
for ($parent = [IO.Directory]::GetParent($Destination); $parent -and -not $parent.Exists; $parent = $parent.Parent) { $missing.Add($parent.FullName) }
for ($i = $missing.Count - 1; $i -ge 0; $i--) { [IO.Directory]::CreateDirectory($missing[$i], $acl) | Out-Null }
[IO.Directory]::CreateDirectory($Destination, $acl) | Out-Null
foreach ($item in $manifest.files) {
  $target = Join-Path $Destination $item.path
  [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
  # Create new destination files so they inherit the private destination ACL;
  # CopyFile may carry security attributes from a publicly extracted source.
  $inputFile = [IO.File]::OpenRead((Join-Path $source $item.path))
  try {
    $outputFile = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $inputFile.CopyTo($outputFile); $outputFile.Flush($true) } finally { $outputFile.Dispose() }
  } finally { $inputFile.Dispose() }
  if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw 'Installed-byte verification failed; preserve this folder for inspection.' }
}
[IO.File]::WriteAllBytes((Join-Path $Destination 'WINDOWS-MANIFEST.json'), [IO.File]::ReadAllBytes((Join-Path $source 'WINDOWS-MANIFEST.json')))
Write-Output ('Installed in ' + $Destination)
Write-Output 'MCP command/args (choose a new private --out path for each run):'
@{ command=(Join-Path $Destination 'python\python.exe'); args=@('-B',(Join-Path $Destination 'env\bin\headgasket-mcp'),'serve','--variant','V1','--out','C:\REPLACE\WITH\NEW\RUN') } | ConvertTo-Json -Depth 3
