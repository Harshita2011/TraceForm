'use client';
import { useCallback, useEffect, useState } from 'react';
import { getSourceLibrary } from '@/lib/api';
import { SourcePage } from '@/lib/types';
export function useSourceLibrary(q='',offset=0,sensitivity='',trash=false) {
  const [data,setData]=useState<SourcePage>({items:[],total:0,offset:0,limit:12});
  const [loading,setLoading]=useState(true);const [error,setError]=useState('');const [version,setVersion]=useState(0);
  const refetch=useCallback(()=>setVersion(v=>v+1),[]);
  useEffect(()=>{let alive=true;setLoading(true);setError('');
    const timer=setTimeout(()=>{getSourceLibrary(q,offset,sensitivity,trash).then(value=>{if(alive)setData(value);}).catch(e=>{if(alive)setError(e.message||'Could not load sources.');}).finally(()=>{if(alive)setLoading(false);});},200);
    return()=>{alive=false;clearTimeout(timer);};
  },[q,offset,sensitivity,trash,version]);
  return {data,loading,error,refetch};
}
