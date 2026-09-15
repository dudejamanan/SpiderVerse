import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { BuildingConfigRequest } from '../types';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.checkHealth(),
    refetchInterval: 8000,
  });
}

export function useBuildingConfig() {
  return useQuery({
    queryKey: ['buildingConfig'],
    queryFn: () => api.getBuildingConfig(),
    staleTime: 60000,
  });
}

export function useLocations() {
  return useQuery({
    queryKey: ['locations'],
    queryFn: () => api.getLocations(),
    staleTime: 300000,
  });
}

export function useRegion() {
  return useQuery({
    queryKey: ['region'],
    queryFn: () => api.getRegion(),
  });
}

export function useTwinState(zoneId: string) {
  return useQuery({
    queryKey: ['twinState', zoneId],
    queryFn: () => api.getTwinState(zoneId),
    refetchInterval: 3500, // 3.5s polling as specified
    enabled: !!zoneId,
  });
}

export function useHistory() {
  return useQuery({
    queryKey: ['history'],
    queryFn: () => api.getHistory(),
    refetchInterval: 5000,
  });
}

// Mutations
export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ zoneId, text }: { zoneId: string; text: string }) =>
      api.submitFeedback(zoneId, text),
    onSuccess: (_, { zoneId }) => {
      queryClient.invalidateQueries({ queryKey: ['twinState', zoneId] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useOptimize() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (zoneId: string) => api.optimize(zoneId),
    onSuccess: (_, zoneId) => {
      queryClient.invalidateQueries({ queryKey: ['twinState', zoneId] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useTestOptimize() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (zoneId: string) => api.testOptimize(zoneId),
    onSuccess: (_, zoneId) => {
      queryClient.invalidateQueries({ queryKey: ['twinState', zoneId] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useConfirmComfort() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ zoneId, comfortable }: { zoneId: string; comfortable: boolean }) =>
      api.confirmComfort(zoneId, comfortable),
    onSuccess: (_, { zoneId }) => {
      queryClient.invalidateQueries({ queryKey: ['twinState', zoneId] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useTestHvac() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ zoneId, hvacPowerW }: { zoneId: string; hvacPowerW: number }) =>
      api.testHvac(zoneId, hvacPowerW),
    onSuccess: (_, { zoneId }) => {
      queryClient.invalidateQueries({ queryKey: ['twinState', zoneId] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useTestConstraint() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (zoneId: string) => api.testConstraint(zoneId),
    onSuccess: (_, zoneId) => {
      queryClient.invalidateQueries({ queryKey: ['twinState', zoneId] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useConfigureBuilding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (req: BuildingConfigRequest) => api.configureBuilding(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['buildingConfig'] });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}

export function useSetRegion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (region: string) => api.setRegion(region),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['region'] });
    },
  });
}
