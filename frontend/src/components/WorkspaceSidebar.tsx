import { NavLink, Link } from 'react-router-dom';
import { BookOpen, History, Home, LineChart, ScanLine, Settings, Sprout, UserRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import LanguageSelector from './LanguageSelector';

export default function WorkspaceSidebar() {
  const { profile, user } = useAuth();
  const { t } = useLanguage();

  const items = [
    { to: '/home', icon: Home, label: t('nav_home') },
    { to: '/scan', icon: ScanLine, label: t('nav_scan') },
    { to: '/market', icon: LineChart, label: t('nav_market') },
    { to: '/advisory', icon: BookOpen, label: t('nav_advisory') },
    { to: '/history', icon: History, label: t('nav_history') },
    { to: '/settings', icon: Settings, label: t('nav_settings') },
  ];
  const displayName = profile?.full_name || user?.user_metadata.full_name || user?.email?.split('@')[0] || t('app_name');

  return (
    <aside className="ks-sidebar" aria-label="Workspace navigation">
      <Link to="/home" className="ks-side-brand">
        <span className="ks-brand-mark"><Sprout size={21} /></span>
        <span>
          <strong>{t('app_name')}</strong>
          <small>FARM WORKSPACE</small>
        </span>
      </Link>

      <p className="ks-side-label">YOUR WORKSPACE</p>
      <nav className="ks-side-nav" aria-label="Workspace">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) => `ks-side-link${isActive ? ' active' : ''}`}
          >
            <Icon size={17} aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="ks-side-bottom">
        <LanguageSelector variant="compact" className="ks-dark-language" />
        <details className="ks-sidebar-profile">
          <summary className="ks-user-chip" aria-label="Show username and email">
            <span className="ks-avatar" aria-hidden="true">
              {displayName === t('app_name') ? <UserRound size={16} /> : displayName.charAt(0).toUpperCase()}
            </span>
            <span className="ks-user-details">
              <strong>{displayName}</strong>
              <small>{user?.email || ''}</small>
            </span>
          </summary>
          <div className="ks-sidebar-profile-popover">
            <strong>{displayName}</strong>
            {user?.email && <span>{user.email}</span>}
          </div>
        </details>
      </div>
    </aside>
  );
}
