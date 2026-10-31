$ErrorActionPreference='Stop'
$base='D:/graghRAG-agent/.tmp/linux-cpu-acceptance-20261029';$own='D:/graghRAG-agent/.tmp/linux-recreation-acceptance-20261029';$patch='D:/graghRAG-agent/.tmp/linux-cpu-patched-artifacts-20261029'
$manifest=Get-Content "$base/staged-inputs.json" -Raw|ConvertFrom-Json
$bad=@();$checked=0
foreach($f in $manifest.files){$path=Join-Path $base $f.relative;$actual=(Get-FileHash $path -Algorithm SHA256).Hash.ToLower();if($actual -ne $f.sha256){$bad+=@{relative=$f.relative;reason='stage-hash'}};if($f.relative -like '*.py' -or $f.relative -match '(Cargo\.toml|Cargo\.lock|main\.rs|build\.py)$'){if((Get-FileHash $f.source -Algorithm SHA256).Hash.ToLower() -ne $f.sha256){$bad+=@{relative=$f.relative;reason='C-source-drift'}}};$checked++}
$map=Get-Content "$patch/artifact-map-all158.json" -Raw|ConvertFrom-Json;$artifactBad=@()
foreach($a in $map.artifacts){$p=Join-Path "$patch/wheels" $a.filename;if((Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne $a.actual_sha256){$artifactBad+=$a.filename}}
[xml]$j=Get-Content "$base/outputs/linux-http-lifecycle-r2.xml" -Raw
$summary=@{staged_checked=$checked;staged_failures=$bad;model_files=$manifest.model_files;artifact_count=$map.count;artifact_failures=$artifactBad;lock_sha256=$map.lock_sha256;junit_tests=$j.testsuites.testsuite.tests;junit_failures=$j.testsuites.testsuite.failures;junit_errors=$j.testsuites.testsuite.errors;junit_skipped=$j.testsuites.testsuite.skipped;timestamp=(Get-Date -Format o)}
$summary|ConvertTo-Json -Depth 8|Set-Content "$own/outputs/independent-input-audit.json"
$summary|ConvertTo-Json -Depth 8
