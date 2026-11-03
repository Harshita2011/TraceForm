'use client';
import {createContext,useContext,useEffect,useState} from 'react';
import Link from 'next/link';
import {usePathname} from 'next/navigation';
import {authStatus,signIn,signOut,switchTeam,teamMe,TeamMe} from '@/lib/teams';
import {IS_DEMO_MODE} from '@/lib/api';
const Context=createContext<{me:TeamMe|null;reload:()=>Promise<void>}>({me:null,reload:async()=>{}});
export const useTeam=()=>useContext(Context);
export function TeamSession({children}:{children:React.ReactNode}) {
  const [me,setMe]=useState<TeamMe|null>(null);const [loading,setLoading]=useState(true);const [setup,setSetup]=useState(false);
  const [mode,setMode]=useState('login');const [email,setEmail]=useState('');const [name,setName]=useState('');const [password,setPassword]=useState('');
  const [key,setKey]=useState('');const [token,setToken]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  const pathname=usePathname();const reload=async()=>{setMe(await teamMe());};
  useEffect(()=>{const expired=()=>{setMe(null);setMode('login');setError('Your session expired. Sign in again to continue.');};window.addEventListener('traceform-session-expired',expired);return()=>window.removeEventListener('traceform-session-expired',expired);},[]);
  useEffect(()=>{if(IS_DEMO_MODE){setLoading(false);return;}let active=true;
    const invite=new URLSearchParams(window.location.hash.slice(1)).get('invite')||new URLSearchParams(window.location.search).get('invite');if(invite){setToken(invite);setMode('accept');window.history.replaceState(null,'',window.location.pathname);setLoading(false);return()=>{active=false;};}
    teamMe().then(value=>{if(active)setMe(value);}).catch(async()=>{try{const s=await authStatus();if(active){setSetup(s.setup_required);if(!invite)setMode('login');}}catch(e){if(active)setError((e as Error).message);}}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};},[]);
  if(IS_DEMO_MODE)return <>{children}</>;
  if(loading)return <main className="team-auth"><p role="status">Opening your workspace…</p></main>;
  if(!me)return <main className="team-auth"><div className="team-auth-card"><p className="eyebrow">TraceForm</p><h1>{mode==='register'?'Create your account':mode==='setup'?'Set up your workspace':mode==='accept'?'Join your team':'Welcome back'}</h1><p className="muted">{mode==='register'?'Get your own private workspace. No invitation or installation key needed.':mode==='setup'?'Installation administrators can claim existing sources and outputs using their admin key.':mode==='accept'?'Use the invited email. Existing accounts use their current password.':'Sign in to access your workspaces and saved work.'}</p>
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{await signIn(mode,{email,password,name:name||email,token:mode==='accept'?token:undefined},key);setPassword('');setKey('');setToken('');await reload();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
    {mode!=='login'&&<label>Your name<input required className="flow-input" autoComplete="name" value={name} onChange={e=>setName(e.target.value)} maxLength={100}/></label>}
    <label>Email<input required type="email" autoComplete="email" className="flow-input" value={email} onChange={e=>setEmail(e.target.value)}/></label>
    <label>{mode==='login'?'Password':'Password (at least 12 characters)'}<input required type="password" autoComplete={mode==='login'?'current-password':'new-password'} minLength={12} maxLength={128} className="flow-input" value={password} onChange={e=>setPassword(e.target.value)}/></label>
    {mode==='setup'&&<label>Installation admin key<input required type="password" autoComplete="off" className="flow-input" value={key} onChange={e=>setKey(e.target.value)}/><small>Use an administrator API key from your installation configuration. It is sent once and is not saved in the browser.</small></label>}
    {mode==='accept'&&<label>Invitation token<input required autoComplete="off" className="flow-input" value={token} onChange={e=>setToken(e.target.value)}/></label>}
    {error&&<p role="alert" className="flow-error">{error}</p>}<button className="flow-button" disabled={busy}>{busy?'Opening…':mode==='register'?'Create account':mode==='login'?'Sign in':mode==='setup'?'Create owner account':'Accept invitation'}</button></form>
    <div className="team-actions"><button type="button" className="flow-button" disabled={busy} onClick={()=>{setMode(mode==='login'?'register':'login');setError('');setPassword('');setKey('');}}>{mode==='login'?'Create account':'Back to sign in'}</button>{mode!=='accept'&&<button type="button" className="quiet-link" disabled={busy} onClick={()=>{setMode('accept');setError('');setPassword('');}}>Join an existing team</button>}{setup&&mode!=='setup'&&<button type="button" className="quiet-link" disabled={busy} onClick={()=>{setMode('setup');setError('');setPassword('');}}>Installation admin setup</button>}</div></div></main>;
  const readOnly=me.role==='viewer'||me.role==='reviewer';
  return <Context.Provider value={{me,reload}}><div className="team-session-bar"><label>Workspace<select aria-label="Active workspace" className="flow-input" value={me.workspace_id} onChange={async e=>{try{await switchTeam(e.target.value);window.location.assign(new URL('/dashboard/generations',window.location.origin).href);}catch(e){setError((e as Error).message);}}}>{me.workspaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label><span>{me.name} · {me.role}</span><button className="quiet-link" onClick={async()=>{try{await signOut();window.location.reload();}catch(e){setError((e as Error).message);}}}>Sign out</button>{error&&<p role="alert">{error}</p>}</div>{readOnly&&<p className="team-readonly">{me.role==='viewer'?'Read-only access: you can view and download workspace outputs.':'Reviewer access: comment and decide assigned reviews. Editors create and change outputs.'}</p>}{readOnly&&pathname==='/dashboard/sources'?<main className="team-auth"><h1>Output creation requires an editor role.</h1><Link href="/dashboard/generations">View workspace outputs</Link></main>:children}</Context.Provider>;
}
