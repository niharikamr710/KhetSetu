import { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import BottomNav from './BottomNav';
import TopNav from './TopNav';
import OfflineBanner from './OfflineBanner';
import WorkspaceSidebar from './WorkspaceSidebar';
import { useAuth } from '../context/AuthContext';

const WORKSPACE_PATHS = ['/home', '/scan', '/result', '/history', '/market', '/advisory', '/settings', '/profile', '/admin'];

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { isAuthenticated } = useAuth();
  const isWorkspace = isAuthenticated && WORKSPACE_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
  const isDashboard = pathname === '/home';

  return (
    <div className={`min-h-screen flex flex-col ${isWorkspace ? 'bg-[#f3f7f4]' : 'bg-leaf-50'}`}>
      {!isWorkspace && <TopNav />}
      <OfflineBanner />
      {isWorkspace ? (
        <main className="flex-1 w-full">
          <div className="ks-dashboard">
            <div className="ks-dashboard-inner">
              <WorkspaceSidebar />
              <div className={`ks-main ${isDashboard ? '' : 'ks-page-surface'}`}>
                {children}
              </div>
            </div>
          </div>
        </main>
      ) : (
        <main className="flex-1 w-full max-w-3xl mx-auto px-4 pt-4 pb-24 md:pb-10">
          {children}
        </main>
      )}
      {!isWorkspace && (
        <footer className="border-t border-leaf-100 px-4 py-4 text-center text-sm text-gray-600">
          <nav aria-label="Information" className="flex justify-center gap-5">
            <a href="/about" className="underline">About</a>
            <a href="/privacy" className="underline">Privacy</a>
            <a href="/terms" className="underline">Terms</a>
          </nav>
        </footer>
      )}
      <BottomNav />
    </div>
  );
}
