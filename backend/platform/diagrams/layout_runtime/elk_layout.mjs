// Installation-owned, one-shot protocol endpoint. Never a user-script runner.
import ELK from 'elkjs/lib/elk.bundled.js';

const MAX_INPUT = 16 * 1024 * 1024;
const MAX_OUTPUT = 32 * 1024 * 1024;
const id = /^(diagram:\/\/|d[ngepl]:|gl:)[0-9a-f]{64}$/;
const hash = /^[0-9a-f]{64}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const profiles = new Set(['architecture_compound_v1', 'dependency_layered_v1', 'static_flow_v1', 'simple_layered_v1']);
const cmp = (a,b) => a < b ? -1 : a > b ? 1 : 0;
function exact(o, keys) {
  if (!o || typeof o !== 'object' || Array.isArray(o) ||
      Object.keys(o).sort().join('|') !== [...keys].sort().join('|')) throw Error('invalid_input');
}
function integer(v, max = 1000000000) {
  if (!Number.isSafeInteger(v) || v < 0 || v > max || Object.is(v, -0)) throw Error('invalid_input');
}
function canonical(v) {
  if (typeof v === 'string') return JSON.stringify(v).replace(/[\u0000-\u001f]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`)
    .replace(/\\([bfnrt])/g, (_, c) => ({b:'\\u0008',f:'\\u000c',n:'\\u000a',r:'\\u000d',t:'\\u0009'}[c]));
  if (v === null || typeof v === 'boolean') return JSON.stringify(v);
  if (typeof v === 'number') { integer(v); return String(v); }
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  return `{${Object.keys(v).sort().map(k => `${canonical(k)}:${canonical(v[k])}`).join(',')}}`;
}
async function readRequest() {
  const parts = []; let length = 0;
  for await (const part of process.stdin) {
    length += part.length;
    if (length > MAX_INPUT + 4) throw Error('capacity');
    parts.push(part);
  }
  const bytes = Buffer.concat(parts);
  if (bytes.length < 4 || bytes.readUInt32BE(0) !== bytes.length - 4) throw Error('invalid_input');
  const body = new TextDecoder('utf-8', {fatal:true}).decode(bytes.subarray(4));
  const r = JSON.parse(body);
  if (canonical(r) !== body) throw Error('invalid_input'); // rejects duplicate wire keys
  exact(r, ['protocol_version','request_id','semantic_digest','profile','nodes','edges','labels']);
  if (r.protocol_version !== 1 || !uuid.test(r.request_id) || !hash.test(r.semantic_digest)) throw Error('invalid_input');
  exact(r.profile, ['id','version','engine','engine_version','runtime_version','font_profile','fingerprint']);
  if (!profiles.has(r.profile.id) || r.profile.version !== '1.0.0' || r.profile.engine !== 'elkjs' ||
      r.profile.engine_version !== '0.12.1' || r.profile.runtime_version !== '24.22.3' ||
      r.profile.font_profile !== 'dejavu_paths_2_37_v1' || !hash.test(r.profile.fingerprint)) throw Error('invalid_input');
  for (const [name,max] of [['nodes',1256],['edges',4000],['labels',100000]]) {
    if (!Array.isArray(r[name]) || r[name].length > max) throw Error('capacity');
  }
  const ids = new Set(), ports = new Set();
  for (const n of r.nodes) {
    exact(n, ['id','parent_id','width','height','ports']);
    if (!id.test(n.id) || !(n.id.startsWith('dn:')||n.id.startsWith('dg:')) || ids.has(n.id) || !Array.isArray(n.ports)) throw Error('invalid_input');
    ids.add(n.id); integer(n.width); integer(n.height);
    if (!n.width || !n.height) throw Error('invalid_input');
    for (const p of n.ports) {
      exact(p, ['id','side','order']); integer(p.order);
      if (!id.test(p.id) || !p.id.startsWith('dp:') || ports.has(p.id) || !['NORTH','SOUTH','EAST','WEST'].includes(p.side)) throw Error('invalid_input');
      ports.add(p.id);
    }
  }
  const byId = new Map(r.nodes.map(n=>[n.id,n]));
  for (const n of r.nodes) {
    const chain = new Set([n.id]); let parent = n.parent_id;
    while (parent !== null) {
      if (!ids.has(parent) || chain.has(parent)) throw Error('invalid_input');
      chain.add(parent); parent = byId.get(parent).parent_id;
    }
  }
  const edgeIds = new Set();
  for (const e of r.edges) {
    exact(e, ['id','source','target']);
    if (!id.test(e.id) || !e.id.startsWith('de:') || edgeIds.has(e.id) || !ids.has(e.source) || !ids.has(e.target)) throw Error('invalid_input');
    edgeIds.add(e.id);
  }
  const labelIds = new Set();
  for (const l of r.labels) {
    exact(l, ['id','owner_id','width','height']); integer(l.width); integer(l.height);
    if (!id.test(l.id) || !l.id.startsWith('dl:') || labelIds.has(l.id) || !(ids.has(l.owner_id) || edgeIds.has(l.owner_id))) throw Error('invalid_input');
    labelIds.add(l.id);
  }
  return r;
}
function write(response) {
  const body = Buffer.from(JSON.stringify(response));
  if (body.length > MAX_OUTPUT) throw Error('capacity');
  const prefix = Buffer.alloc(4); prefix.writeUInt32BE(body.length);
  process.stdout.write(prefix); process.stdout.write(body);
}
async function layout(r) {
  const simple = r.profile.id === 'simple_layered_v1';
  const options = {
    'elk.algorithm':'layered', 'elk.direction':'DOWN', 'elk.randomSeed':'42',
    'elk.edgeRouting': simple ? 'POLYLINE':'ORTHOGONAL',
    'elk.hierarchyHandling':'INCLUDE_CHILDREN', 'elk.spacing.nodeNode':'40',
    'elk.layered.spacing.nodeNodeBetweenLayers':'60',
    'elk.padding':'[top=48,left=24,bottom=24,right=24]',
    // Edges are declared at root even when ELK assigns a nested container.
    // Normalize their routes/labels to root coordinates before shelf packing.
    'elk.json.edgeCoords':'ROOT',
  };
  const children = new Map(r.nodes.map(n=>[n.id, []]));
  const roots = [];
  for (const n of [...r.nodes].sort((a,b)=>cmp(a.id,b.id))) {
    const node = {id:n.id,width:n.width/1000,height:n.height/1000,children:children.get(n.id),layoutOptions:options,
      ports:simple ? [] : [...n.ports].sort((a,b)=>a.order-b.order || cmp(a.id,b.id)).map(p=>({id:p.id,width:0,height:0,layoutOptions:{'elk.port.side':p.side,'elk.port.index':String(p.order)}})),
      labels:r.labels.filter(l=>l.owner_id===n.id).map(l=>({id:l.id,width:l.width/1000,height:l.height/1000}))};
    if (n.parent_id === null || simple) roots.push(node); else children.get(n.parent_id).push(node);
  }
  const parent = new Map(r.nodes.map(n=>[n.id,n.id]));
  function find(x) { while(parent.get(x)!==x) { parent.set(x,parent.get(parent.get(x))); x=parent.get(x); } return x; }
  function union(a,b) { const x=find(a),y=find(b); if(x!==y) parent.set(cmp(x,y)<0?y:x,cmp(x,y)<0?x:y); }
  for(const n of r.nodes) if(n.parent_id!==null) union(n.id,n.parent_id);
  for(const e of r.edges) union(e.source,e.target);
  const components = new Map();
  for(const n of r.nodes) { const key=find(n.id); if(!components.has(key)) components.set(key,new Set()); components.get(key).add(n.id); }
  const geometry = {nodes:[],groups:[],ports:[],labels:[],routes:[],bounds:{x:0,y:0,width:0,height:0}};
  const groupIds = new Set(r.nodes.filter(n=>n.id.startsWith('dg:')).map(n=>n.id));
  function visit(n, dx, dy) {
    const x=dx+(n.x||0), y=dy+(n.y||0);
    if (n.id !== 'root') (groupIds.has(n.id)?geometry.groups:geometry.nodes).push({id:n.id,box:{x,y,width:n.width,height:n.height}});
    for (const p of n.ports||[]) geometry.ports.push({id:p.id,owner_id:n.id,point:{x:x+p.x,y:y+p.y}});
    for (const l of n.labels||[]) geometry.labels.push({id:l.id,owner_id:n.id,box:{x:x+(l.x||0),y:y+(l.y||0),width:l.width,height:l.height}});
    for (const e of n.edges||[]) {
      geometry.routes.push({edge_id:e.id,sections:(e.sections||[]).map(s=>({start:{x:x+s.startPoint.x,y:y+s.startPoint.y},bends:(s.bendPoints||[]).map(p=>({x:x+p.x,y:y+p.y})),end:{x:x+s.endPoint.x,y:y+s.endPoint.y}}))});
      for (const l of e.labels||[]) geometry.labels.push({id:l.id,owner_id:e.id,box:{x:x+(l.x||0),y:y+(l.y||0),width:l.width,height:l.height}});
    }
    for (const child of n.children||[]) visit(child,x,y);
  }
  let x=0,y=0,rowHeight=0;
  for(const [key, members] of [...components.entries()].sort((a,b)=>cmp(a[0],b[0]))) {
    const graph = {id:'root',layoutOptions:options,children:roots.filter(n=>members.has(n.id)),
      edges:[...r.edges].filter(e=>members.has(e.source)).sort((a,b)=>cmp(a.id,b.id)).map(e=>({id:e.id,sources:[e.source],targets:[e.target],
        // ELK ignores empty-text labels even with measured dimensions. Pass
        // only their opaque IDs (never source text) and label-scoped placement
        // so the engine reserves space instead of stacking them at (0,0).
        labels:r.labels.filter(l=>l.owner_id===e.id).map(l=>({id:l.id,text:l.id,width:l.width/1000,height:l.height/1000,
          layoutOptions:{'org.eclipse.elk.edgeLabels.placement':'CENTER'}}))}))};
    const output=await new ELK().layout(graph);
    if(!Number.isFinite(output.width)||!Number.isFinite(output.height)||output.width>1000000||output.height>1000000) throw Error('capacity');
    if(x && x+output.width>1600) { x=0; y+=rowHeight+80; rowHeight=0; }
    visit(output,x,y);
    geometry.bounds.width=Math.max(geometry.bounds.width,x+output.width);
    geometry.bounds.height=Math.max(geometry.bounds.height,y+output.height);
    rowHeight=Math.max(rowHeight,output.height); x+=output.width+80;
  }
  if(simple && geometry.groups.length) {
    const boxes=new Map([...geometry.nodes,...geometry.groups].map(n=>[n.id,n.box]));
    const input=new Map(r.nodes.map(n=>[n.id,n]));
    const complete=new Set();
    function enclose(id) {
      if(complete.has(id)) return boxes.get(id);
      const children=r.nodes.filter(n=>n.parent_id===id).map(n=>groupIds.has(n.id)?enclose(n.id):boxes.get(n.id));
      if(children.length) {
        const left=Math.min(...children.map(b=>b.x))-24;
        const top=Math.min(...children.map(b=>b.y))-48;
        boxes.set(id,{x:left,y:top,width:Math.max(...children.map(b=>b.x+b.width))-left+24,
          height:Math.max(...children.map(b=>b.y+b.height))-top+24});
      }
      complete.add(id); return boxes.get(id);
    }
    for(const group of geometry.groups) group.box=enclose(group.id);
    for(const label of geometry.labels) if(groupIds.has(label.owner_id)) {
      const box=boxes.get(label.owner_id); label.box.x=box.x+24; label.box.y=box.y+12;
    }
    const edges=new Map(r.edges.map(e=>[e.id,e]));
    for(const route of geometry.routes) {
      const edge=edges.get(route.edge_id);
      if(!groupIds.has(edge.source)&&!groupIds.has(edge.target)) continue;
      const a=boxes.get(edge.source),b=boxes.get(edge.target);
      const start={x:a.x+a.width/2,y:a.y+a.height},end={x:b.x+b.width/2,y:b.y};
      const middle=(start.y+end.y)/2;
      route.sections=[{start,bends:[{x:start.x,y:middle},{x:end.x,y:middle}],end}];
      for(const label of geometry.labels) if(label.owner_id===edge.id) {
        label.box.x=(start.x+end.x-label.box.width)/2; label.box.y=middle;
      }
    }
    const points=[];
    const boxPoints=b=>points.push({x:b.x,y:b.y},{x:b.x+b.width,y:b.y+b.height});
    for(const n of [...geometry.nodes,...geometry.groups,...geometry.labels]) boxPoints(n.box);
    for(const route of geometry.routes) for(const s of route.sections) points.push(s.start,...s.bends,s.end);
    let left=0,top=0,right=0,bottom=0;
    for(const p of points) { left=Math.min(left,p.x);top=Math.min(top,p.y);right=Math.max(right,p.x);bottom=Math.max(bottom,p.y); }
    for(const n of [...geometry.nodes,...geometry.groups,...geometry.labels]) { n.box.x-=left; n.box.y-=top; }
    for(const route of geometry.routes) for(const s of route.sections) for(const p of [s.start,...s.bends,s.end]) { p.x-=left;p.y-=top; }
    geometry.bounds={x:0,y:0,width:right-left,height:bottom-top};
  }
  return geometry;
}
let request;
try {
  if (process.versions.node !== '24.22.3') throw Error('invalid_input');
  request = await readRequest();
  const geometry = await layout(request);
  write({protocol_version:1,request_id:request.request_id,semantic_digest:request.semantic_digest,
    profile_fingerprint:request.profile.fingerprint,geometry});
} catch (error) {
  if (request) write({protocol_version:1,request_id:request.request_id,error:['invalid_input','capacity'].includes(error.message)?error.message:'layout_failed'});
  process.exitCode=1;
}
