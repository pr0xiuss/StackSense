"""Fresh-process C2/protocol measurements, NOT ELK/FS/browser capacity proof."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.p5.diagrams.test_database import diagram_db as diagram_db


@pytest.mark.skipif(
    os.environ.get("M4_B1_ESSENTIAL_PROOFS") != "1",
    reason="opt-in real pinned rootless ELK capacity measurement",
)
@pytest.mark.parametrize("count", [20, 150, 500])
def test_fresh_process_b3_layout_and_export_measurement(count):
    script = r"""
import gc,hashlib,json,os,resource,time
from pathlib import Path
from types import SimpleNamespace
from backend.platform.delivery.contracts import DiagramTemplate as T
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.export import prepare_layout,member_payloads
from backend.platform.diagrams.fonts import DiagramFonts
from backend.platform.diagrams.layout import LockedFile,create_layout_profile
from tests.p5.diagrams.test_builders import entity,relation,data,build
from tests.p5.diagrams.test_exports import Control
from tests.p5.integration.test_diagram_pipeline import RealRootlessLayout
def rss():
    lines=Path('/proc/self/status').read_text().splitlines()
    return next(int(l.split()[1])*1024 for l in lines if l.startswith('VmRSS:'))
before=rss(); count=COUNT
paths={'node':Path(os.environ['M4_B1_NODE']),'bwrap':Path(os.environ['M4_B1_BWRAP']),
       'helper':Path('backend/platform/diagrams/layout_runtime/elk_layout.mjs'),
       'elk':Path('backend/platform/diagrams/layout_runtime/node_modules/elkjs/lib/elk.bundled.js')}
lock=SimpleNamespace(files=tuple(LockedFile(path=k,
    sha256=hashlib.sha256(v.read_bytes()).hexdigest())
    for k,v in sorted(paths.items())))
entities=tuple(entity(i+1) for i in range(count))
relationships=tuple(relation(i+1,entities[i],entities[i+1])
    for i in range(count-1) if i%5 != 4)
started=time.perf_counter(); built=build(data(entities,relationships),T.DEPENDENCY)
built_at=time.perf_counter(); fonts=DiagramFonts()
try:
    profile=create_layout_profile('dependency_layered_v1',lock,fonts.manifest_digest())
    layout=prepare_layout(built,fonts,RealRootlessLayout(),profile,
        DiagramLimits(),time.monotonic()+180,Control())
finally: fonts.close()
laid_out=time.perf_counter()
payloads=member_payloads(built,layout,DiagramLimits(),lambda:None)
finished=time.perf_counter(); after=rss(); gc.collect()
assert len(layout.nodes)==count
print(json.dumps({'scope':('real rootless ELK + prepared SVG; '
    'not production RSS/OS/store certification'),
    'nodes':count,'edges':len(layout.routes),'build_seconds':built_at-started,
    'layout_font_seconds':laid_out-built_at,'export_seconds':finished-laid_out,
    'members':{k:len(v) for k,v in payloads.items()},
    'layout_digest':layout.layout_digest,
    'current_rss_before':before,'current_rss_after':after,'current_rss_after_gc':rss(),
    'fresh_process_peak_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024},sort_keys=True))
""".replace("COUNT", str(count))
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=200
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout.strip())
    assert value["nodes"] == count
    print("M4_B3_LAYOUT_EXPORT_MEASUREMENT " + json.dumps(value, sort_keys=True))


@pytest.mark.skipif(
    sys.platform != "linux",
    reason=(
        "Fresh-process /proc/self/status and POSIX resource"
        " measurements require Linux"
    ),
)
@pytest.mark.parametrize("count", [20, 150, 500])
def test_fresh_process_contract_scene_measurements(count):
    script = r"""
import gc,json,platform,resource,time
from pathlib import Path
from backend.platform.diagrams.configuration import DiagramLimits
from backend.platform.diagrams.layout import LayoutScene,RuntimeNode,RuntimeEdge
from backend.platform.diagrams.model import visual_id
count=COUNT
def rss():
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'): return int(line.split()[1])*1024
before=rss()
nodes=tuple(RuntimeNode(id=visual_id('node',i),parent_id=None,
                       width=240000,height=80000,ports=()) for i in range(count))
edges=tuple(RuntimeEdge(id=visual_id('edge',i),source=nodes[i].id,
                       target=nodes[i+1].id) for i in range(count-1))
scene=LayoutScene(nodes=nodes,edges=edges,labels=())
permuted=LayoutScene(nodes=tuple(reversed(nodes)),edges=tuple(reversed(edges)),labels=())
raw=scene.to_bytes()
assert raw==permuted.to_bytes()
assert len(raw)<=DiagramLimits().max_helper_input_bytes
measurements=[]
for kind in ('cold','warm'):
    for repeat in range(10):
        started=time.perf_counter()
        if kind=='cold':
            value=LayoutScene.from_bytes(
                raw,max_bytes=DiagramLimits().max_helper_input_bytes)
        else: value=scene
        assert value.to_bytes()==raw
        measurements.append({'kind':kind,'repeat':repeat,'seconds':time.perf_counter()-started})
after=rss();gc.collect()
print(json.dumps({'scope':'C2/protocol only; not ELK, DB, seal or browser proof',
                  'python':platform.python_version(),'machine':platform.machine(),'nodes':count,
                  'edges':count-1,'bytes':len(raw),'current_rss_before':before,
                  'current_rss_after':after,'current_rss_after_gc':rss(),
                  'fresh_process_peak_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                  'measurements':measurements}))
""".replace("COUNT", str(count))
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        env={"LANG": "C.UTF-8", "TZ": "UTC", "PYTHONHASHSEED": "0"},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    measured = json.loads(result.stdout)
    assert measured["nodes"] == count
    assert len(measured["measurements"]) == 20
    print("M4_B1_CONTRACT_MEASUREMENT " + json.dumps(measured, sort_keys=True))


@pytest.mark.skipif(
    sys.platform != "linux",
    reason=(
        "Fresh-process /proc/self/status and POSIX resource"
        " measurements require Linux"
    ),
)
@pytest.mark.parametrize("count", [20, 150, 500])
def test_fresh_process_four_b2_builder_measurements(count):
    """Measure actual semantic builders separately from ELK/store/pytest peak."""
    script = r"""
import gc,json,resource,time
from pathlib import Path
from tests.p5.diagrams.test_builders import entity,relation,data
from backend.platform.analysis.architecture.model import ArchitectureEntityKind as K
from backend.platform.analysis.architecture.model import (
    ArchitectureRelationshipKind as R,
)
from backend.platform.diagrams.builders import BUILDERS
from backend.platform.diagrams.configuration import DiagramLimits
def rss():
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'): return int(line.split()[1])*1024
count=COUNT
before=rss()
nodes=tuple(entity(i+1,K.APPLICATION if i==0 else K.SERVICE) for i in range(count))
edges=tuple(relation(i,nodes[(i-1)//20],nodes[i],R.CONTAINS) for i in range(1,count))
edges+=tuple(relation(10000+i,nodes[i-1],nodes[i],R.CALLS) for i in range(1,count))
source=data(nodes,edges)
results=[]
for template,builder in BUILDERS.items():
    expected=None
    for repeat in range(3):
        started=time.perf_counter()
        built=builder.build(source,DiagramLimits())
        raw=built.spec.to_bytes()
        assert len(built.spec.nodes)==count
        if expected is not None: assert raw==expected
        expected=raw
        results.append(dict(template=template.value,repeat=repeat,seconds=time.perf_counter()-started,
                            nodes=len(built.spec.nodes),edges=len(built.spec.edges),groups=len(built.spec.groups),
                            spec_bytes=len(raw),catalog_bytes=len(built.catalog.to_bytes())))
after=rss();gc.collect()
print(json.dumps(dict(scope=('B2 semantic builders only; '
                            'not paging/ELK/sealing or production capacity approval'),
                     count=count,results=results,current_rss_before=before,current_rss_after=after,
                     current_rss_after_gc=rss(),fresh_process_peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)))
""".replace("COUNT", str(count))
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        env={"LANG": "C.UTF-8", "TZ": "UTC", "PYTHONHASHSEED": "0"},
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    measured = json.loads(completed.stdout)
    assert len(measured["results"]) == 12
    assert {result["nodes"] for result in measured["results"]} == {count}
    print("M4_B2_BUILDER_MEASUREMENT " + json.dumps(measured, sort_keys=True))


@pytest.fixture
def canonical_capacity_db(request):
    if os.environ.get("M4_CANONICAL_MEASUREMENT") != "1":
        pytest.skip("explicit actual M4 canonical boundary measurement required")
    if not os.environ.get("P5_TEST_DATABASE_URL"):
        pytest.fail("enabled canonical measurement requires disposable PostgreSQL")
    return request.getfixturevalue("diagram_db")


def test_public_canonical_25k_entities_50k_relationships(canonical_capacity_db):
    """Real public read boundary; not maximum evidence/ELK/physical proof."""
    import gc
    import hashlib
    from dataclasses import replace
    from time import monotonic

    from sqlalchemy.orm import Session

    from backend.platform.analysis.architecture.model import (
        ArchitectureRelationshipKind,
        build_entity_logical_id,
        build_relationship_logical_id,
        semantic_signature,
    )
    from backend.platform.analysis.architecture.persistence import (
        SqlAlchemyArchitectureRepository,
    )
    from backend.platform.diagrams.configuration import DiagramLimits
    from backend.platform.diagrams.contracts import CanonicalDiagramScope
    from backend.platform.diagrams.query import SourceBudget, canonical_read_source
    from backend.platform.projects.infra.base import Base
    from tests.p3.analysis.test_m4_persistence import _analysis, _document, _validated

    engine, schema, url = canonical_capacity_db
    Base.metadata.create_all(engine)
    base = _document()
    seed = base.entities[0]
    entities = tuple(
        replace(
            seed,
            logical_id=build_entity_logical_id(
                project_id=base.project_id,
                repository_id=base.repository_id,
                kind=seed.kind,
                namespace_parts=seed.namespace,
                anchor_parts=(f"node-{i:06d}",),
            ),
            name=f"Node{i:06d}",
            semantic_signature=semantic_signature({"node": i}),
        )
        for i in range(25000)
    )
    kind = ArchitectureRelationshipKind.DEPENDS_ON
    edges = tuple(
        replace(
            base.relationships[0],
            kind=kind,
            source_logical_id=entities[i].logical_id,
            target_logical_id=entities[(i + offset) % 25000].logical_id,
            logical_id=build_relationship_logical_id(
                project_id=base.project_id,
                repository_id=base.repository_id,
                kind=kind,
                source_logical_id=entities[i].logical_id,
                target_logical_id=entities[(i + offset) % 25000].logical_id,
            ),
        )
        for i in range(25000)
        for offset in (1, 2)
    )
    document = replace(
        base,
        content_digest="",
        entities=entities,
        relationships=edges,
        unresolved_relationships=(),
        conflicts=(),
        completeness=replace(
            base.completeness,
            source_entities=25000,
            source_relationships=50000,
            source_unresolved_references=0,
            source_conflicts=0,
            architecture_entities=25000,
            architecture_relationships=50000,
            architecture_unresolved_relationships=0,
            architecture_conflicts=0,
        ),
    )
    with Session(engine) as session:
        _analysis(session, document)
        repo = SqlAlchemyArchitectureRepository(session)
        repo.reserve_version(document)
        repo.mark_validating(document.architecture_version_id, document.analysis_id)
        repo.publish(_validated(document))
        session.commit()
    scope = CanonicalDiagramScope(
        project_id=document.project_id,
        repository_id=document.repository_id,
        analysis_id=document.analysis_id,
        snapshot_id=document.snapshot_id,
        architecture_version_id=document.architecture_version_id,
        sequence_number=1,
        canonical_digest=document.content_digest,
        architecture_schema_version="1.0.0",
        ir_schema_version="1.0.0",
    )
    # Fixture construction is deliberately not retained by the production-like
    # page scan. Peak RSS still includes imports/fixture publication and is
    # labeled as lifetime accounting, never a 512 MiB parser-worker proof.
    del document, entities, edges, base, seed

    def rss():
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
        raise RuntimeError("current RSS unavailable")

    expected = None
    for repeat in range(2):
        gc.collect()
        before_rss = rss()
        started = monotonic()
        budget = SourceBudget(DiagramLimits(), started + 180, lambda: None)
        digest = hashlib.sha256()
        counts = {}
        with canonical_read_source(url, budget, read_schema=schema) as source:
            for collection in (
                "entities",
                "relationships",
                "evidence",
                "unresolved",
                "conflicts",
            ):
                count = 0
                for record in source.scan(collection, scope, budget):
                    digest.update(record.to_bytes())
                    count += 1
                counts[collection] = count
        assert counts == {
            "entities": 25000,
            "relationships": 50000,
            "evidence": 1,
            "unresolved": 0,
            "conflicts": 0,
        }
        if expected is not None:
            assert digest.hexdigest() == expected
        expected = digest.hexdigest()
        after_rss = rss()
        gc.collect()
        print(
            "M4_B1_CANONICAL_MEASUREMENT "
            + json.dumps(
                {
                    "repeat": repeat,
                    "seconds": monotonic() - started,
                    "counts": counts,
                    "calls": budget.calls,
                    "rows": budget.rows,
                    "bytes": budget.bytes,
                    "digest": expected,
                    "rss_before": before_rss,
                    "rss_after": after_rss,
                    "rss_after_gc": rss(),
                    "scope": "public paging only; not layout/sealing proof",
                },
                sort_keys=True,
            )
        )
