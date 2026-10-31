# Private Linux CPU lock — root continuation 2026-10-29

Actual resolver generated lock SHA d1434b9b8b46f3d9c061098e15ddaada44e8d0a2d3dfb55d4db4c425a8f60b36. Standard online uv lock --check exit0,46.641seconds, before/after lock SHA identical. Original offline check exit2 is retained: canonical URL metadata cache miss. Check resolution used Windows CPython3.12.8, not an actual Linux installed runtime. Target graph is constrained Linux x86_64/Python3.12; runtime133 and all-groups158 exclude the virtual backend root (resolver159 includes root).

Private amendment replaces the earlier named-index draft with exact official PEP508 direct Torch CPU URL plus official SHA fragment. tool.uv.sources URL hash-fragment parser rejection remains historical. No manual lock node deletion, no formal C pyproject/lock/default-device modification. Official expected wheel digest and lock digest are not by themselves an independent SHA rehash of a retained complete wheel; no such whole-wheel attestation is claimed here. No installation/model/backend container acceptance or native security conclusion follows from lock consistency.

Independent full graph review pending. Formal production gate remains compatibility_not_approved. This archival is documentation only, no commit/push/deploy/migration.
