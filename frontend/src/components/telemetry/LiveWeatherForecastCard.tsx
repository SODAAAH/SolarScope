import React from 'react';
import { Link } from 'react-router-dom';
import {
  Sun,
  Moon,
  Cloud,
  CloudSun,
  CloudRain,
  CloudDrizzle,
  CloudLightning,
  CloudFog,
  Wind,
  Droplets,
  RefreshCw,
  MapPin,
  ArrowUpRight
} from 'lucide-react';
import type { WeatherIntelligenceResponse } from '../../lib/api';
import { formatHourLabel12 } from '../../lib/formatters';
import { Tooltip } from '../common/Tooltip';

interface LiveWeatherForecastCardProps {
  weather: WeatherIntelligenceResponse | null;
  loading?: boolean;
  onRefresh?: () => void;
}

const renderWeatherIcon = (iconKey?: string, className = 'w-5 h-5') => {
  switch (iconKey) {
    case 'sun':
      return <Sun className={`${className} text-amber-500`} aria-hidden="true" />;
    case 'moon':
      return <Moon className={`${className} text-slate-400`} aria-hidden="true" />;
    case 'cloud-sun':
      return <CloudSun className={`${className} text-amber-500`} aria-hidden="true" />;
    case 'cloud-rain':
      return <CloudRain className={`${className} text-sky-500`} aria-hidden="true" />;
    case 'cloud-drizzle':
      return <CloudDrizzle className={`${className} text-sky-400`} aria-hidden="true" />;
    case 'cloud-lightning':
      return <CloudLightning className={`${className} text-amber-600`} aria-hidden="true" />;
    case 'cloud-fog':
      return <CloudFog className={`${className} text-slate-400`} aria-hidden="true" />;
    case 'cloud':
    default:
      return <Cloud className={`${className} text-slate-500 dark:text-slate-400`} aria-hidden="true" />;
  }
};

export const LiveWeatherForecastCard: React.FC<LiveWeatherForecastCardProps> = ({
  weather,
  loading = false,
  onRefresh
}) => {
  if (weather && weather.configured === false) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 flex items-center justify-center shrink-0">
            <MapPin className="w-4 h-4" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Live Cloud &amp; Weather Forecast
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {weather.message || 'Set site latitude and longitude in System Settings to display live cloud cover and weather conditions.'}
            </p>
          </div>
        </div>
        <Link
          to="/settings"
          className="self-start sm:self-auto shrink-0 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-medium transition-colors"
        >
          Configure Location
        </Link>
      </div>
    );
  }

  const current = weather?.current_conditions;
  const liveHours = weather?.live_hourly_forecast || [];
  const tomorrow = weather?.tomorrow_forecast;
  const coordsText =
    weather && weather.latitude !== undefined && weather.longitude !== undefined && (weather.latitude !== 0 || weather.longitude !== 0)
      ? `${Math.abs(weather.latitude).toFixed(2)}° ${weather.latitude >= 0 ? 'N' : 'S'}, ${Math.abs(weather.longitude).toFixed(2)}° ${weather.longitude >= 0 ? 'E' : 'W'}`
      : '';
  const cloudPct = current ? Math.max(0, Math.min(100, current.cloud_cover_percent ?? 0)) : 0;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-xs space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 border-b border-slate-100 dark:border-slate-800 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Tooltip
            title="Live Site Weather & Cloud Forecast"
            content="Live meteorological sky conditions, cloud cover density, irradiance, and rolling 12-hour forecast from Open-Meteo for your site coordinates."
            provenance="Measured"
            position="bottom"
          >
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 cursor-help">
              Live Weather &amp; Cloud Forecast
            </h3>
          </Tooltip>
          {weather?.location && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-600 dark:text-slate-300">
              <MapPin className="w-3 h-3 text-slate-400" aria-hidden="true" />
              <span>{weather.location}</span>
              {coordsText && <span className="text-slate-400 font-mono hidden sm:inline">({coordsText})</span>}
            </span>
          )}
          {current?.condition_label && (
            <span className="px-2 py-0.5 rounded-md bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 text-[11px] font-medium">
              {current.condition_label}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700 text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
              <span>{loading ? 'Updating' : 'Refresh'}</span>
            </button>
          )}
          <Link
            to="/solar?tab=weather"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-[11px] font-medium text-slate-700 dark:text-slate-200 transition-colors"
          >
            <span>Solar Weather</span>
            <ArrowUpRight className="w-3 h-3" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {!current ? (
        <div className="py-6 text-center text-xs text-slate-500 dark:text-slate-400">
          {loading ? 'Loading live weather and cloud forecast...' : (weather?.message || 'Live weather forecast unavailable right now.')}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
          <div className="lg:col-span-4 rounded-lg bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 p-3.5 flex flex-col justify-between gap-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 flex items-center justify-center shrink-0">
                  {renderWeatherIcon(current.icon_key, 'w-6 h-6')}
                </div>
                <div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums leading-tight">
                    {current.temperature_c.toFixed(1)}°C
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-400 font-medium">
                    {current.condition_label || 'Current Sky'}
                  </div>
                </div>
              </div>

              <div className="text-right">
                <div className="text-[11px] text-slate-500 dark:text-slate-400">Cloud Cover</div>
                <div className="text-base font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                  {cloudPct.toFixed(0)}%
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <div className="h-1.5 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                <div
                  className="h-full rounded-full bg-sky-500 transition-[width] duration-200"
                  style={{ width: `${cloudPct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400">
                <span>Clear</span>
                <span>Partly</span>
                <span>Overcast</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-200/70 dark:border-slate-700/70 text-[11px]">
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Irradiance</span>
                <span className="font-semibold text-amber-600 dark:text-amber-400 tabular-nums">
                  {current.solar_radiation_wm2.toFixed(0)} W/m²
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Rain</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums inline-flex items-center gap-1">
                  <Droplets className="w-3 h-3 text-sky-500" aria-hidden="true" />
                  {(current.precipitation_mm ?? 0).toFixed(1)} mm
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Wind</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 tabular-nums inline-flex items-center gap-1">
                  <Wind className="w-3 h-3 text-slate-400" aria-hidden="true" />
                  {(current.wind_speed_kmh ?? 0).toFixed(0)} km/h
                </span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-8 flex flex-col justify-between gap-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="font-medium text-slate-700 dark:text-slate-300">
                Hourly Cloud &amp; Sky Timeline (Next 12 Hours)
              </span>
              {tomorrow && (
                <span className="text-[11px] text-slate-500 dark:text-slate-400 tabular-nums">
                  Tomorrow: <strong className="text-slate-700 dark:text-slate-200">{tomorrow.average_cloud_cover_percent.toFixed(0)}% avg clouds</strong>
                  {tomorrow.expected_solar_kwh > 0 ? ` · Est. ${tomorrow.expected_solar_kwh.toFixed(1)} kWh PV` : ''}
                </span>
              )}
            </div>

            <div className="grid grid-cols-3 sm:grid-cols-6 xl:grid-cols-12 gap-2">
              {liveHours.map((slot) => {
                const slotCloud = Math.max(0, Math.min(100, slot.cloud_cover_percent ?? 0));
                return (
                  <div
                    key={slot.time}
                    className={`rounded-lg border p-2 flex flex-col items-center justify-between gap-1.5 text-center ${
                      slot.is_now
                        ? 'bg-amber-50/70 dark:bg-amber-950/25 border-amber-300 dark:border-amber-800/70'
                        : 'bg-slate-50/60 dark:bg-slate-800/30 border-slate-200/80 dark:border-slate-800'
                    }`}
                  >
                    <span className={`text-[10px] font-mono ${slot.is_now ? 'font-bold text-amber-700 dark:text-amber-300' : 'text-slate-500 dark:text-slate-400'}`}>
                      {slot.is_now ? 'Now' : formatHourLabel12(slot.hour)}
                    </span>

                    <div className="my-0.5" title={slot.condition_label || ''}>
                      {renderWeatherIcon(slot.icon_key, 'w-4 h-4')}
                    </div>

                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                      {slot.temperature_c.toFixed(0)}°
                    </span>

                    <div className="w-full space-y-0.5">
                      <div className="text-[10px] font-mono text-slate-600 dark:text-slate-300 tabular-nums">
                        {slotCloud.toFixed(0)}%
                      </div>
                      <div className="h-1 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-sky-500"
                          style={{ width: `${slotCloud}%` }}
                        />
                      </div>
                    </div>

                    <span className="text-[9px] text-slate-400 tabular-nums">
                      {(slot.precipitation_mm ?? 0) > 0
                        ? `${slot.precipitation_mm?.toFixed(1)}mm`
                        : `${slot.solar_radiation_wm2.toFixed(0)}W`}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
