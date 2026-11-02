'use client';
import { useEffect, useState } from 'react';
import { getPresets, savePreset, deletePreset } from '@/lib/api';
import { CreationPreset } from '@/lib/types';
export function PresetPicker({settings,onApply}:{settings:CreationPreset['settings'];onApply:(settings:CreationPreset['settings'])=>void}) {
 const [items,setItems]=useState<CreationPreset[]>([]);const [selected,setSelected]=useState('');const [name,setName]=useState('');
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');const [confirm,setConfirm]=useState(false);
 const current=items.find(p=>p.id===selected);
 const load=async()=>{try{setItems(await getPresets());setError('');}catch(e){setError((e as Error).message);}};
 useEffect(()=>{void load();},[]);
 const save=async(update:boolean)=>{setBusy(true);setError('');try{const value=await savePreset(name,settings,update?current:undefined);setItems(v=>[value,...v.filter(i=>i.id!==value.id)]);setSelected(value.id);setNotice('Preset saved on the server.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
 const remove=async()=>{if(!current)return;setBusy(true);try{await deletePreset(current.id);setItems(v=>v.filter(p=>p.id!==current.id));setSelected('');setName('');setConfirm(false);setNotice('Preset removed. Current preferences are kept.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
 return <details className="advanced-settings preset-picker"><summary>Saved presets <span>Reuse your writing preferences</span></summary><p className="muted mt-4">Personal to this operator. Saves formats, audience, tone, language, length, goal, sections and brand guidance. Source, privacy and budget stay separate.</p>
 <label className="flow-label">Apply a preset<select disabled={busy} className="flow-input" value={selected} onChange={e=>{setSelected(e.target.value);setConfirm(false);const value=items.find(i=>i.id===e.target.value);if(value){setName(value.name);onApply(value.settings);setNotice('Preset applied. You can adjust it before creating.');}}}><option value="">Choose a saved preset</option>{items.map(i=><option value={i.id} key={i.id}>{i.name}</option>)}</select></label>
 <label className="flow-label">Preset name<input className="flow-input" value={name} maxLength={80} onChange={e=>setName(e.target.value)} placeholder="For example: Leadership updates" /></label><div className="settings-actions"><button className="flow-button secondary" disabled={busy||!name.trim()} onClick={()=>save(false)}>Save as new</button>{current&&<><button className="flow-button secondary" disabled={busy||!name.trim()} onClick={()=>save(true)}>Update preset</button><button className="quiet-link" disabled={busy} onClick={()=>setConfirm(!confirm)}>Remove preset</button></>}</div>
 {confirm&&<div className="flow-error"><p>Remove “{current?.name}”? Existing runs and current preferences are kept.</p><button className="flow-button secondary mt-3" disabled={busy} onClick={remove}>Confirm removal</button></div>}
 {error&&<div role="alert" className="flow-error">{error}<button className="quiet-link" onClick={load}>Reload presets</button></div>}{notice&&<p role="status" className="muted mt-3">{notice}</p>}</details>;
}
