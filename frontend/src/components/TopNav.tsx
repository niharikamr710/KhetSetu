import { NavLink, Link } from 'react-router-dom';
import { Home, ScanLine, LineChart, History, Settings, Sprout, BookOpen } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import LanguageSelector from './LanguageSelector';

export default function TopNav({ dark = false }: { dark?: boolean }) {
  const { t } = useLanguage();

  const items = [
    { to: '/home', icon: Home, label: t('nav_home') },
    { to: '/scan', icon: ScanLine, label: t('nav_scan') },
    { to: '/market', icon: LineChart, label: t('nav_market') },
    { to: '/advisory', icon: BookOpen, label: t('nav_advisory') },
    { to: '/history', icon: History, label: t('nav_history') },
    { to: '/settings', icon: Settings, label: t('nav_settings') },
  ];

  return (
    <header className={`hidden md:flex items-center justify-between px-8 py-4 sticky top-0 z-40 ${dark ? 'bg-[#101a1c] border-b border-[#253739]' : 'bg-white border-b border-leaf-100'}`}>
      <Link to="/" className={`flex items-center gap-2 font-extrabold text-xl ${dark ? 'text-white' : 'text-leaf-800'}`}>
        <span className="bg-leaf-600 text-white rounded-xl p-2 flex items-center justify-center">
          <Sprout size={22} />
        </span>
        {t('app_name')}
      </Link>

      <nav className="flex items-center gap-1">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                isActive
                  ? dark ? 'bg-[#1d3334] text-emerald-200' : 'bg-leaf-100 text-leaf-800'
                  : dark ? 'text-slate-400 hover:bg-[#1a292b] hover:text-white' : 'text-gray-500 hover:bg-leaf-50'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <LanguageSelector variant="compact" />
    </header>
  );
}
