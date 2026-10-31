$ErrorActionPreference='Stop';$own='D:/graghRAG-agent/.tmp/linux-recreation-acceptance-20261029';$base='D:/graghRAG-agent/.tmp/linux-cpu-acceptance-20261029';$c='C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent'
$receipts=@();$ids=@()
foreach($phase in 1..3){$i=(Get-Content "$own/outputs/phase-$phase-inspect.json" -Raw|ConvertFrom-Json)[0];$e=Get-Content "$own/outputs/phase-$phase-exit.json" -Raw|ConvertFrom-Json
if($i.Image -ne 'sha256:f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83' -or $i.State.ExitCode -ne 0 -or $i.State.OOMKilled -or $e.exit -ne 0){throw 'identity/exit failure'}
$h=$i.HostConfig;if(!$h.ReadonlyRootfs -or $h.NetworkMode -ne 'none' -or $h.NanoCpus -ne 2000000000 -or $h.Memory -ne 4294967296 -or $h.PidsLimit -ne 128 -or $i.Config.User -ne '65534:65534' -or $i.Config.WorkingDir -ne '/source/backend' -or 'ALL' -notin $h.CapDrop -or 'no-new-privileges' -notin $h.SecurityOpt){throw 'container restriction mismatch'}
foreach($m in $i.Mounts){if($m.Type -eq 'bind' -and $m.RW){$s=$m.Source.Replace('\','/').TrimEnd('/');if($s -notmatch 'linux-recreation-acceptance-20261029/(outputs|data|uploads|output)$'){throw "unexpected rw $s"}};if($m.Destination -in @('/source','/models/bge-small-zh-v1.5') -and $m.RW){throw 'source/model rw'}}
$ids+=$i.Id;$receipts+=@{phase=$phase;id=$i.Id;image=$i.Image;exit=$i.State.ExitCode;seconds=$e.seconds;mounts=$i.Mounts;host_config=$h;user=$i.Config.User;cwd=$i.Config.WorkingDir}
}
if(($ids|Select-Object -Unique).Count -ne 3){throw 'not distinct containers'}
$native=@();foreach($rel in @('Cargo.toml','Cargo.lock','rust-toolchain.toml','src/main.rs','build.py')){$left=Join-Path "$base/source/backend/native/vector_numeric" $rel;$right=Join-Path "$c/backend/native/vector_numeric" $rel;$sha=(Get-FileHash $left -Algorithm SHA256).Hash.ToLower();if($sha -ne (Get-FileHash $right -Algorithm SHA256).Hash.ToLower()){throw 'C source drift'};$native+=@{relative=$rel;sha256=$sha}}
$receipts|ConvertTo-Json -Depth 15|Set-Content "$own/outputs/container-restrictions-receipt.json"
$native|ConvertTo-Json|Set-Content "$own/outputs/native-source-identity.json"
@{container_ids=$ids;distinct=3;all_zero_exit=$true;actual_image_restrictions_and_rw_alias_checked=$true;source_native4_and_build_py_match_C=$true;formal_linux_build_gate='closed: Linux release build and validation are not yet approved';scope='Private synthetic build identity only; three-container service-level recovery with real pinned model; existing HTTP22 separately evidenced'}|ConvertTo-Json -Depth 5|Set-Content "$own/receipt.json"
