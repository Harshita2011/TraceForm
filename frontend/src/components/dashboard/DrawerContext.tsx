'use client';
import { createContext, useContext } from 'react';
import { Artifact } from '@/lib/types';
export const DrawerContext = createContext<{
  openDrawer: (artifact: Artifact) => void;
  closeDrawer: () => void;
}>({ openDrawer: () => {}, closeDrawer: () => {} });
export const useDrawer = () => useContext(DrawerContext);
