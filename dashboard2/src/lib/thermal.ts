/**
 * Thermal Physics color language & telemetry utilities
 */

export interface TempColorInfo {
  hex: string;
  label: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
}

export function getThermalColor(tempC: number): TempColorInfo {
  if (tempC < 18.0) {
    return {
      hex: '#38bdf8',
      label: 'CRYO / UNDERCOOLED',
      badgeBg: 'bg-sky-500/10',
      badgeText: 'text-sky-400',
      badgeBorder: 'border-sky-500/30',
    };
  }
  if (tempC < 21.0) {
    return {
      hex: '#06b6d4',
      label: 'COOL',
      badgeBg: 'bg-cyan-500/10',
      badgeText: 'text-cyan-400',
      badgeBorder: 'border-cyan-500/30',
    };
  }
  if (tempC <= 24.0) {
    return {
      hex: '#10b981',
      label: 'OPTIMAL COMFORT',
      badgeBg: 'bg-emerald-500/10',
      badgeText: 'text-emerald-400',
      badgeBorder: 'border-emerald-500/30',
    };
  }
  if (tempC <= 26.0) {
    return {
      hex: '#f59e0b',
      label: 'ELEVATED TEMP',
      badgeBg: 'bg-amber-500/10',
      badgeText: 'text-amber-400',
      badgeBorder: 'border-amber-500/30',
    };
  }
  if (tempC <= 28.0) {
    return {
      hex: '#f97316',
      label: 'OVERHEAT WARNING',
      badgeBg: 'bg-orange-500/10',
      badgeText: 'text-orange-400',
      badgeBorder: 'border-orange-500/30',
    };
  }
  return {
    hex: '#ef4444',
    label: 'CRITICAL HOT',
    badgeBg: 'bg-red-500/10',
    badgeText: 'text-red-400',
    badgeBorder: 'border-red-500/30',
  };
}

export function getCo2Status(ppm: number): { label: string; color: string } {
  if (ppm < 600) return { label: 'OPTIMAL AIR QUALITY', color: '#10b981' };
  if (ppm < 1000) return { label: 'ACCEPTABLE VENTILATION', color: '#f59e0b' };
  return { label: 'POOR AIR QUALITY / STUFFY', color: '#ef4444' };
}

export function formatEnergy(kw: number): string {
  return `${kw.toFixed(2)} kW`;
}

export function formatTemp(c: number): string {
  return `${c.toFixed(1)}°C`;
}
