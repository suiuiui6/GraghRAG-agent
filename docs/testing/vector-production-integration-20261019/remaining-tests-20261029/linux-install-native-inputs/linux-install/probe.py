import hashlib,json,math,os,pathlib,stat,sys
sys.path.insert(0,'/app')
import vector_numeric as n
kind=sys.argv[1]
root=pathlib.Path('/app/native/vector_numeric')
binary=root/'bin/x86_64-unknown-linux-gnu/vector-numeric-bridge'
manifest=binary.parent/'approved-build.json'
out={'kind':kind,'uid':os.getuid(),'checks':[]}
assert os.getuid()==65534
if kind!='good':
    try:n.parse('1.5')
    except n.NumericBridgeUnavailable as e:
        assert str(e)=='numeric bridge unavailable';out['safe_failure']=True
    else:raise AssertionError('expected safe bridge failure')
else:
    assert n._verified_binary()==binary
    value=json.loads(manifest.read_text());assert value['approved'] is True
    assert len(manifest.read_bytes())<=8192
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(binary)=='20d2166cd218fdd0dff2914939c07e400fa38231f06139b91689ee45279418d0'
    assert {**{f:sha(root/f) for f in n._SOURCE_FILES},binary.name:sha(binary)}==value['files']
    out['manifest_bytes']=len(manifest.read_bytes());out['binary_sha256']=sha(binary)
    out['modes']={str(p):{'mode':oct(stat.S_IMODE(p.stat().st_mode)),'uid':p.stat().st_uid} for p in [root,binary,manifest,root/'src/main.rs']}
    assert stat.S_IMODE(binary.stat().st_mode)==0o555
    assert stat.S_IMODE(manifest.stat().st_mode)==0o444
    for token,expected in [('0',('u64',0)),('9223372036854775807',('u64',2**63-1)),('9223372036854775808',('u64',2**63)),('18446744073709551615',('u64',2**64-1)),('-9223372036854775808',('i64',-2**63)),('1.5',('f64',1.5))]:
        assert n.parse(token)==expected;out['checks'].append('where:'+token)
    for integer in [-2**63,0,2**63-1]:assert n.record_ingress(integer)==('i64',integer)
    for number in [-0.0,1.5,1.7976931348623157e308,2**63,2**64]:
        tag,v=n.record_ingress(number);assert tag=='f64' and math.isfinite(v)
    assert math.copysign(1,n.record_ingress(-0.0)[1])==1
    for bad in [float('nan'),float('inf'),float('-inf'),10**400]:
        try:n.record_ingress(bad)
        except ValueError:pass
        else:raise AssertionError('nonfinite accepted')
    for p in [binary,manifest,root/'src/main.rs']:
        try:
            with p.open('ab') as f:f.write(b'forbidden')
        except OSError:out['checks'].append('write_denied:'+str(p))
        else:raise AssertionError('write succeeded')
    for parent in [binary.parent,root,root/'src',root.parent,pathlib.Path('/app')]:
        try:(parent/'forbidden-write-probe').write_bytes(b'forbidden')
        except OSError:out['checks'].append('create_denied:'+str(parent))
        else:raise AssertionError('create succeeded')
    out['checks'].append('metadata_formatter_and_nonfinite_boundaries')
print(json.dumps(out))
