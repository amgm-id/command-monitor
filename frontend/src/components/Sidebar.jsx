import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard, Terminal, Users, Server, Shield,
  LogIn, Activity, FileBarChart, UserCog, ChevronRight
} from 'lucide-react'
import { alertsApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import clsx from 'clsx'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/commands', icon: Terminal, label: 'Command History' },
  { to: '/sessions/active', icon: Activity, label: 'Active Sessions' },
  { to: '/sessions/history', icon: LogIn, label: 'Login History' },
  { to: '/servers', icon: Server, label: 'Servers' },
  { to: '/alerts', icon: Shield, label: 'Alerts', badge: true },
  { to: '/reports', icon: FileBarChart, label: 'Reports' },
  { to: '/users', icon: UserCog, label: 'User Management', roles: ['super_admin', 'admin'] },
]

export default function Sidebar() {
  const { hasRole } = useAuth()
  const { data: alertCount } = useQuery({
    queryKey: ['alert-count'],
    queryFn: () => alertsApi.unreadCount().then((r) => r.data.count),
    refetchInterval: 30_000,
  })

  return (
    <aside className="w-60 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Shield className="w-4.5 h-4.5 text-white" size={18} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">ServerAgent</p>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Monitor</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-4 px-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          if (item.roles && !hasRole(...item.roles)) return null
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-100',
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                )
              }
            >
              <item.icon size={16} className="flex-shrink-0" />
              <span className="flex-1">{item.label}</span>
              {item.badge && alertCount > 0 && (
                <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                  {alertCount > 99 ? '99+' : alertCount}
                </span>
              )}
            </NavLink>
          )
        })}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <p className="text-[10px] text-gray-600 text-center">ServerAgent Monitor v1.0</p>
      </div>
    </aside>
  )
}
