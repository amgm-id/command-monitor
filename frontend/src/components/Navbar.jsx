import { useAuth } from '../contexts/AuthContext'
import { LogOut, User, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const ROLE_LABELS = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  auditor: 'Auditor',
  viewer: 'Viewer',
}

const ROLE_COLORS = {
  super_admin: 'text-purple-400',
  admin: 'text-blue-400',
  auditor: 'text-yellow-400',
  viewer: 'text-gray-400',
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6 flex-shrink-0">
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs text-gray-500">Live monitoring active</span>
      </div>

      <div className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 text-sm text-gray-300 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-gray-800"
        >
          <div className="w-7 h-7 bg-blue-600 rounded-full flex items-center justify-center">
            <User size={14} className="text-white" />
          </div>
          <div className="text-left">
            <p className="text-xs font-medium text-white">{user?.full_name || user?.username}</p>
            <p className={`text-[10px] ${ROLE_COLORS[user?.role] || 'text-gray-500'}`}>
              {ROLE_LABELS[user?.role] || user?.role}
            </p>
          </div>
          <ChevronDown size={14} className="text-gray-500" />
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-1 w-44 bg-gray-800 border border-gray-700 rounded-lg shadow-xl py-1 z-50">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-gray-700 hover:text-red-300 transition-colors"
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
