$ErrorActionPreference='Stop'
$base='D:/graghRAG-agent/.tmp/linux-cpu-acceptance-20261029'
$own='D:/graghRAG-agent/.tmp/linux-recreation-acceptance-20261029'
$image='sha256:f4e637023bdc366728472bcaa271002d2d69ad6065c6bd6e7b706ed9c4d1df83'
foreach($phase in 1..3){
$name="graphrag-independent-recreation-20261029-$phase"
$args=@('run','--name',$name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534','--cpus','2','--memory','4g','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,size=1073741824,mode=1777','--workdir','/source/backend')
foreach($mount in @("type=bind,src=$base/source,dst=/source,readonly","type=bind,src=$base/model,dst=/models/bge-small-zh-v1.5,readonly","type=bind,src=$base/model-receipt-linux.json,dst=/model-receipt.json,readonly","type=bind,src=$own/runner.py,dst=/runner.py,readonly","type=bind,src=$own/outputs,dst=/evidence","type=bind,src=$own/data,dst=/fixtures","type=bind,src=$own/uploads,dst=/source/backend/uploads","type=bind,src=$own/output,dst=/source/backend/output")){$args+=@('--mount',$mount)}
foreach($envval in @('TMPDIR=/fixtures','PYTHONPATH=/source/backend','PYTHON_DOTENV_DISABLED=1','HF_HUB_OFFLINE=1','TRANSFORMERS_OFFLINE=1','HF_HOME=/tmp/hf','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2')){$args+=@('--env',$envval)}
$args+=@($image,'timeout','240','python','-B','/runner.py',"$phase")
$args|ConvertTo-Json|Set-Content "$own/outputs/phase-$phase-command.json"
$watch=[Diagnostics.Stopwatch]::StartNew(); & docker @args *> "$own/outputs/phase-$phase.log"; $code=$LASTEXITCODE
& docker inspect $name > "$own/outputs/phase-$phase-inspect.json"
@{exit=$code;seconds=$watch.Elapsed.TotalSeconds;name=$name}|ConvertTo-Json|Set-Content "$own/outputs/phase-$phase-exit.json"
if($code -ne 0){Get-Content "$own/outputs/phase-$phase.log";throw "phase $phase failed $code"}
}
