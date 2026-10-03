import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  Camera,
  CheckCircle2,
  Clock3,
  Leaf,
  LineChart,
  MapPin,
  ScanLine,
  Sprout,
  UserRound,
} from 'lucide-react';
import ModelStatus from '../components/ModelStatus';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { getHistory, saveLastResult } from '../services/storageService';
import { HistoryItem, localName } from '../types';

export default function DashboardPage() {
  const { profile, user } = useAuth();
  const { t, language, availableLanguages } = useLanguage();
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryItem[]>([]);

  useEffect(() => {
    setHistory(getHistory());
  }, []);

  const locale = availableLanguages.find((item) => item.code === language)?.locale ?? 'en';
  const today = new Intl.DateTimeFormat(locale, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date());
  const latestScan = history[0];
  const displayName = profile?.full_name || user?.user_metadata.full_name || user?.email?.split('@')[0] || t('app_name');
  const farmArea = profile?.farm_size == null || profile.farm_size === ''
    ? null
    : String(profile.farm_size);

  const cropActivity = useMemo(() => {
    const counts = new Map<string, { crop: string; count: number }>();
    history.forEach((item) => {
      const crop = localName(item, 'crop', language);
      const current = counts.get(crop);
      counts.set(crop, { crop, count: (current?.count ?? 0) + 1 });
    });
    return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, 4);
  }, [history, language]);
  const maxActivity = Math.max(1, ...cropActivity.map((item) => item.count));

  const viewLatestResult = () => {
    if (latestScan?.result) saveLastResult(latestScan.result);
    navigate(latestScan?.result ? '/result' : '/history');
  };

  return (
    <div className="ks-home-content">
      <header className="ks-welcome-panel ks-panel">
        <div>
          <p className="ks-eyebrow">{today} <span aria-hidden="true">·</span> {t('nav_home')}</p>
          <h1>{t('welcome')}{profile?.full_name ? `, ${profile.full_name}` : ''}</h1>
          <p className="ks-welcome-copy">Your crops, health checks, and market information — all in one place.</p>
        </div>
        <div className="ks-welcome-actions">
          {profile?.district && (
            <span className="ks-location">
              <MapPin size={15} aria-hidden="true" />
              {profile.district}
            </span>
          )}
          <details className="ks-profile-menu">
            <summary className="ks-profile-link" aria-label="Show account name and email">
              <span className="ks-avatar" aria-hidden="true">
                {profile?.full_name?.charAt(0).toUpperCase() || <UserRound size={16} />}
              </span>
            </summary>
            <div className="ks-profile-popover">
              <strong>{displayName}</strong>
              {user?.email && <span>{user.email}</span>}
            </div>
          </details>
        </div>
      </header>

      <section className="ks-stats-grid" aria-label="Farm overview">
        <Link to="/profile" className="ks-stat-card ks-panel">
          <div className="ks-stat-heading">
            <span className="ks-eyebrow">FARM AREA</span>
            <span className="ks-stat-icon"><Sprout size={19} /></span>
          </div>
          <strong className="ks-stat-value">{farmArea ?? 'Add details'}</strong>
          <span className="ks-stat-caption">
            {farmArea ? 'Registered farm size' : 'Complete your farm profile'}
          </span>
        </Link>

        <Link to="/history" className="ks-stat-card ks-panel">
          <div className="ks-stat-heading">
            <span className="ks-eyebrow">CROP RECORDS</span>
            <span className="ks-stat-icon"><Clock3 size={19} /></span>
          </div>
          <strong className="ks-stat-value">{history.length.toString().padStart(2, '0')}</strong>
          <span className="ks-stat-caption">Saved scans on this device</span>
        </Link>

        <Link to="/advisory" className="ks-stat-card ks-voice-panel ks-panel">
          <div className="ks-stat-heading">
            <span className="ks-eyebrow">FARMER ADVISORY</span>
            <span className="ks-stat-icon"><BookOpen size={19} /></span>
          </div>
          <strong className="ks-stat-value">Crop care</strong>
          <span className="ks-stat-caption">Practical guidance for supported crops</span>
        </Link>
      </section>

      <section className="ks-grid-main" aria-label="Crop health and activity">
        <div className="ks-panel ks-activity-panel">
          <div className="ks-section-heading">
            <div>
              <p className="ks-eyebrow">YOUR FIELD PROFILE</p>
              <h2>Crop scan activity</h2>
            </div>
            <span className="ks-activity-badge">{history.length} {history.length === 1 ? 'scan' : 'scans'}</span>
          </div>

          {cropActivity.length ? (
            <div className="ks-activity-list">
              {cropActivity.map(({ crop, count }) => (
                <div className="ks-activity-row" key={crop}>
                  <span className="ks-activity-crop"><Leaf size={16} aria-hidden="true" />{crop}</span>
                  <span className="ks-activity-track" aria-label={`${count} scans`}>
                    <span style={{ width: `${Math.max(8, (count / maxActivity) * 100)}%` }} />
                  </span>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="ks-empty-activity">
              <span className="ks-empty-icon"><ScanLine size={22} /></span>
              <div>
                <strong>Your crop activity will show here</strong>
                <p>Scan a leaf to start building your private, on-device crop record.</p>
              </div>
            </div>
          )}

          <div className="ks-panel-footer">
            <span><i className="ks-dot ks-dot-green" /> Scans saved on this device</span>
            <Link to="/history" className="ks-inline-link">View history <ArrowRight size={15} /></Link>
          </div>
        </div>

        <div className="ks-panel ks-diagnosis-panel">
          <div className="ks-section-heading">
            <div>
              <p className="ks-eyebrow">PRECISION FARMING · AI</p>
              <h2>Crop health diagnosis</h2>
            </div>
            <ModelStatus compact />
          </div>

          {latestScan ? (
            <div className="ks-latest-scan">
              {latestScan.thumbnail ? (
                <img src={latestScan.thumbnail} alt="" className="ks-latest-thumb" />
              ) : (
                <span className="ks-latest-thumb ks-latest-placeholder"><Camera size={20} /></span>
              )}
              <div className="ks-latest-details">
                <span className="ks-muted">Latest saved scan</span>
                <strong>{localName(latestScan, 'crop', language)} · {latestScan.is_healthy ? t('healthy_leaf') : localName(latestScan, 'disease', language)}</strong>
                <span className="ks-confidence">{Math.round(latestScan.confidence * 100)}% confidence</span>
              </div>
            </div>
          ) : (
            <div className="ks-empty-diagnosis">
              <CheckCircle2 size={22} />
              <div>
                <strong>No crop scans yet</strong>
                <p>Your latest diagnosis will appear here after your first scan.</p>
              </div>
            </div>
          )}

          <p className="ks-diagnosis-note">A diagnosis is only shown when the model is confident enough.</p>
          <Link to="/scan" className="ks-primary-action">
            <Camera size={17} /> Start a crop scan <ArrowRight size={16} />
          </Link>
          {latestScan && (
            <button type="button" onClick={viewLatestResult} className="ks-secondary-link">
              View latest result
            </button>
          )}
        </div>
      </section>

      <section className="ks-quick-links" aria-label="Farm tools">
        <Link to="/market" className="ks-quick-link ks-panel">
          <span className="ks-quick-icon"><LineChart size={19} /></span>
          <span><strong>Market prices</strong><small>Check mandi prices and source status</small></span>
          <ArrowRight size={17} />
        </Link>
        <Link to="/advisory" className="ks-quick-link ks-panel">
          <span className="ks-quick-icon"><BookOpen size={19} /></span>
          <span><strong>Crop advisory</strong><small>Explore disease and crop care guidance</small></span>
          <ArrowRight size={17} />
        </Link>
      </section>

    </div>
  );
}
