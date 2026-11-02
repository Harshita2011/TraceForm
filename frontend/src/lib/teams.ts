import { apiFetch } from './api';
export type TeamRole='owner'|'editor'|'reviewer'|'viewer';
export interface TeamMe {user_id:string;email:string;name:string;role:TeamRole;workspace_id:string;workspaces:{id:string;name:string;role:TeamRole}[]}
export interface TeamMember {id:string;name:string;email:string;role:TeamRole}
export interface TeamReview {id:string;version_id:string;artifact_id:string;requester:string;assignee:string;content_hash:string;status:string;revision:number;created_at:string;content?:string;label?:string;decision?:{actor:string;reason:string;decision:string;created_at:string}|null}
export interface TeamComment {id:string;version_id:string;parent_id:string|null;actor:string;body:string;resolved:boolean;created_at:string}
export const teamMe=()=>apiFetch<TeamMe>('/api/v1/auth/me');
export const authStatus=()=>apiFetch<{setup_required:boolean;authenticated:boolean}>('/api/v1/auth/status');
export const signIn=(mode:string,data:{email:string;password:string;name:string;token?:string},key='')=>apiFetch('/api/v1/auth/'+mode,{method:'POST',headers:key?{'X-Installation-Key':key}:{},body:JSON.stringify(data)});
export const signOut=()=>apiFetch('/api/v1/auth/logout',{method:'POST'});
export const switchTeam=(workspace_id:string)=>apiFetch('/api/v1/auth/switch',{method:'POST',body:JSON.stringify({workspace_id})});
export const createTeam=(name:string)=>apiFetch<{id:string}>('/api/v1/team-workspaces',{method:'POST',body:JSON.stringify({name})});
export const teamMembers=()=>apiFetch<TeamMember[]>('/api/v1/team-members');
export const memberRole=(id:string,role:TeamRole)=>apiFetch('/api/v1/team-members/'+id,{method:'PUT',body:JSON.stringify({role})});
export const removeMember=(id:string)=>apiFetch('/api/v1/team-members/'+id,{method:'DELETE'});
export const teamInvite=(email:string,role:TeamRole)=>apiFetch<{id:string;token:string;expires_at:string}>('/api/v1/team-invitations',{method:'POST',body:JSON.stringify({email,role})});
export interface TeamInvitation {id:string;email:string;role:TeamRole;expires_at:string;accepted:boolean;revoked:boolean}
export const invitations=()=>apiFetch<TeamInvitation[]>('/api/v1/team-invitations');
export const revokeInvite=(id:string)=>apiFetch('/api/v1/team-invitations/'+id,{method:'DELETE'});
export const requestTeamReview=(version_id:string,assignee:string)=>apiFetch<TeamReview>('/api/v1/team-reviews',{method:'POST',body:JSON.stringify({version_id,assignee})});
export const teamReviews=(status='pending',mine=true,offset=0)=>apiFetch<{items:TeamReview[];total:number}>(`/api/v1/team-reviews?${new URLSearchParams({status,mine:String(mine),offset:String(offset)})}`);
export const teamReview=(id:string)=>apiFetch<TeamReview>('/api/v1/team-reviews/'+id);
export const decideReview=(id:string,decision:string,reason:string,expected_revision:number)=>apiFetch('/api/v1/team-reviews/'+id+'/decision',{method:'POST',body:JSON.stringify({decision,reason,expected_revision})});
export const teamApproval=(id:string)=>apiFetch<{status:string;content_hash:string}>('/api/v1/team-versions/'+id+'/approval');
export const teamComments=(id:string,offset=0)=>apiFetch<TeamComment[]>(`/api/v1/team-comments?version_id=${encodeURIComponent(id)}&offset=${offset}`);
export const addComment=(version_id:string,body:string,parent_id?:string)=>apiFetch('/api/v1/team-comments',{method:'POST',body:JSON.stringify({version_id,body,parent_id})});
export const resolveComment=(id:string,resolved:boolean)=>apiFetch(`/api/v1/team-comments/${id}/resolve?resolved=${resolved}`,{method:'PUT'});
export interface TeamActivity {id:string;actor:string;action:string;resource_id:string|null;created_at:string;details:Record<string,string>}
export const teamActivity=(q='',actor='',action='',offset=0)=>apiFetch<{items:TeamActivity[];total:number}>('/api/v1/team-activity?'+new URLSearchParams({q,actor,action,offset:String(offset)}));
