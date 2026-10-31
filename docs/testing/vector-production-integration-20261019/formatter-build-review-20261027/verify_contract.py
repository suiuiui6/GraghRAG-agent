import datetime,difflib,hashlib,json,pathlib
out=pathlib.Path(__file__).resolve().parent
c=pathlib.Path('C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent')
d=out.parent/'vector-contract-update-20261027'
pairs={'ingress': 'docs/contracts/2026-10-14-vector-ingress-semantics.md','design':'docs/design/2026-10-19-vector-production-integration.md','plan':'docs/plans/2026-10-19-vector-production-integration.md'}
records=[]
for name,target in pairs.items():
    baseline=c/target; candidate=d/(name+'.md')
    b=baseline.read_bytes(); a=candidate.read_bytes()
    old=b.decode('utf-8-sig').splitlines(); new=a.decode('utf-8-sig').splitlines()
    changes=[{'op':op,'old_lines':old[i:j],'new_lines':new[k:l]} for op,i,j,k,l in difflib.SequenceMatcher(a=old,b=new,autojunk=False).get_opcodes() if op!='equal']
    if name=='ingress':
        assert len(changes)==3
        assert changes[0]['op']=='insert' and changes[1]['old_lines']==['## R5记录入口新证据及错误契约']
        assert changes[2]['op']=='insert'
    if name=='design':
        assert len(changes)==1 and len(changes[0]['old_lines'])==len(changes[0]['new_lines'])==1
        gates=[x for x in old if '默认生产启动返回compatibility_not_approved' in x]
        assert len(gates)==1 and gates[0] in new
    if name=='plan':
        assert len(changes)==1 and changes[0]['op']=='insert'
        assert [x for x in old if '[ ]' in x]==[x for x in new if '[ ]' in x]
    records.append({'candidate':str(candidate),'target':str(baseline),'baseline_sha256':hashlib.sha256(b).hexdigest(),'candidate_sha256':hashlib.sha256(a).hexdigest(),'normalized_changes':changes})
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':0,'scope':'document candidates only; line-ending normalization for diff only, hashes bind actual bytes','records':records}
(out/'contract-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({x['candidate']:x['candidate_sha256'] for x in records},indent=2))
