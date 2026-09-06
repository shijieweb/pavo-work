import { useNavigate, useLocation } from 'react-router-dom';
import { Outlet } from 'react-router-dom';
import { FolderKanban, Plus, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', label: '项目', icon: FolderKanban },
  { path: '/new', label: '新建', icon: Plus },
  { path: '/settings', label: '设置', icon: Settings },
];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border bg-surface sticky top-0 z-40">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div
              className="flex items-center gap-2 cursor-pointer"
              onClick={() => navigate('/')}
            >
              <div className="w-7 h-7 rounded-sm bg-accent flex items-center justify-center">
                <span className="text-accent-on text-sm font-medium">R</span>
              </div>
              <span className="text-base font-medium text-fg">ReqFlow</span>
            </div>

            <nav className="flex items-center gap-1" aria-label="主导航">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path ||
                  (item.path !== '/new' && location.pathname.startsWith(item.path));

                return (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-sm text-sm transition-colors duration-150',
                      'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-opacity-30',
                      isActive
                        ? 'text-accent bg-accent/10 font-medium'
                        : 'text-muted hover:text-fg hover:bg-surface-warm'
                    )}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
