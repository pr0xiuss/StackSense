import React from 'react';
import { render, act, waitFor, fireEvent } from '@testing-library/react';
import { describe,it,expect,vi } from 'vitest';
import { diagramFixture } from '../diagramFixtures.js';
import { DiagramCanvas, DiagramNode } from '../../src/components/diagrams/DiagramCanvas.jsx';
const control=vi.hoisted(()=>({init:null,nodes:null,edges:null,camera:{fitView:vi.fn(),setCenter:vi.fn()}}));
vi.mock('@xyflow/react',()=>({ReactFlowProvider:({children})=>children,ReactFlow:({onInit,nodes,edges})=>{control.init=onInit;control.nodes=nodes;control.edges=edges;return <div/>},Controls:()=>null,Handle:()=>null,Position:{Top:'top',Bottom:'bottom'},useReactFlow:()=>control.camera}));
describe('camera initialization and selection',()=>{
  it('reuses routes and prepared node data when selection changes',()=>{
    const value=diagramFixture(),state={base_generation_id:value.descriptor.reference.generation_id,base_digest:value.spec.semantic_digest,collapsed_groups:[],selected_ref:null};
    const props={spec:value.spec,layout:value.layout,viewState:state,onSelect:vi.fn(),onFocus:vi.fn(),onToggleGroup:vi.fn()};
    const {rerender}=render(<DiagramCanvas {...props}/>);
    const data=new Map(control.nodes.map(node=>[node.id,node.data])),edges=control.edges;
    rerender(<DiagramCanvas {...props} viewState={{...state,selected_ref:value.spec.nodes[0].entity}}/>);
    expect(control.edges).toBe(edges);
    control.nodes.forEach(node=>expect(node.data).toBe(data.get(node.id)));
    expect(control.nodes.filter(node=>node.selected).map(node=>node.id)).toEqual([value.spec.nodes[0].id]);
  });
  it('keeps fixed node controls pointer-interactive and stops pane selection clearing',()=>{
    const value=diagramFixture(),item=value.spec.nodes[0],onSelect=vi.fn(),pane=vi.fn();
    const {getByRole}=render(<div onClick={pane}><DiagramNode data={{item,box:{width:240000,height:80000},labels:[],glyphs:new Map(),onSelect}}/></div>);
    const node=getByRole('button');
    expect(getComputedStyle(node).pointerEvents).toBe('auto');
    fireEvent.click(node);
    expect(onSelect).toHaveBeenCalledWith(item.entity);
    expect(pane).not.toHaveBeenCalled();
  });
  it('suppresses a late initial fit after the user has selected; explicit focus is one-shot',async()=>{
    const value=diagramFixture(),node=value.spec.nodes[0];
    const state={base_generation_id:value.descriptor.reference.generation_id,base_digest:value.spec.semantic_digest,collapsed_groups:[],selected_ref:node.entity};
    const props={spec:value.spec,layout:value.layout,viewState:state,onSelect:vi.fn(),onFocus:vi.fn(),onToggleGroup:vi.fn()};
    const {rerender}=render(<DiagramCanvas {...props}/>);
    act(()=>control.init());
    expect(control.camera.fitView).not.toHaveBeenCalled();
    const request={id:node.id,sequence:1};
    rerender(<DiagramCanvas {...props} viewState={{...state,focus_visual_id:request}}/>);
    await waitFor(()=>expect(control.camera.setCenter).toHaveBeenCalledTimes(1));
    rerender(<DiagramCanvas {...props} viewState={{...state,selected_ref:null,focus_visual_id:request}}/>);
    expect(control.camera.setCenter).toHaveBeenCalledTimes(1);
    expect(control.camera.fitView).not.toHaveBeenCalled();
  });
});
