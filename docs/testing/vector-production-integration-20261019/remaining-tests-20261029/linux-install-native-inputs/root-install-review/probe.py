import sys,json,math,os
sys.path.insert(0,'/app')
import vector_numeric as n
kind=sys.argv[1]
assert os.getuid()==65534
if kind=='good':
    assert n.record_ingress(float.fromhex('0x1.fffffffffffffp+62'))==('f64',float(2**63))
    assert n.parse('9223372036854775808')==('u64',2**63)
    try:n.parse('1e309')
    except ValueError:pass
    else:raise AssertionError('nonfinite parser accepted')
    p=n._verified_binary()
    for q in [p,p.parent/'approved-build.json',p.parent.parent]:
        assert not os.access(q,os.W_OK)
else:
    try:n.parse('1')
    except n.NumericBridgeUnavailable as e:assert str(e)=='numeric bridge unavailable'
    else:raise AssertionError('bad package accepted')
print(json.dumps({'kind':kind,'uid':os.getuid(),'pass':True}))
