import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboardApi } from '../services/api'
import { formatDateTime, formatTime, TIMEZONE_LABEL } from '../utils/datetime'
import {
  AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  Terminal, Shield, Server, Activity, Wifi
} from 'lucide-react'
import RiskBadge from '../components/RiskBadge'
import { useState, useEffect } from 'react'
import { onWsEvent } from '../services/websocket'

const RISK_COLORS = { critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e' }

function StatCard({ icon: Icon, label, value, sub, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-600/10 text-blue-400 border-blue-500/20',
    red: 'bg-red-600/10 text-red-400 border-red-500/20',
    green: 'bg-green-600/10 text-green-400 border-green-500/20',
    yellow: 'bg-yellow-600/10 text-yellow-400 border-yellow-500/20',
    purple: 'bg-purple-600/10 text-purple-400 border-purple-500/20',
  }
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center border ${colors[color]}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value ?? '—'}</p>
        <p className="text-xs text-gray-500 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [period, setPeriod] = useState('24h')
  const queryClient = useQueryClient()

  // Auto-refresh when agent sends new data via WebSocket
  useEffect(() => {
    const unsub1 = onWsEvent('new_commands', () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      queryClient.invalidateQueries({ queryKey: ['activity-chart', period] })
    })
    const unsub2 = onWsEvent('new_alerts', () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
      queryClient.invalidateQueries({ queryKey: ['alert-count'] })
    })
    const unsub3 = onWsEvent('server_heartbeat', () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    })
    return () => { unsub1(); unsub2(); unsub3() }
  }, [period, queryClient])

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.stats().then((r) => r.data),
    refetchInterval: 30_000,
  })

  const { data: chart } = useQuery({
    queryKey: ['activity-chart', period],
    queryFn: () => dashboardApi.activityChart(period).then((r) => r.data),
    refetchInterval: 60_000,
  })

  const { data: riskDist } = useQuery({
    queryKey: ['risk-distribution'],
    queryFn: () => dashboardApi.riskDistribution({}).then((r) => r.data),
    refetchInterval: 60_000,
  })

  if (isLoading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" /></div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Real-time server activity overview</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Terminal} label="Commands Today" value={stats?.total_commands_today?.toLocaleString()} sub={`${stats?.total_commands_week?.toLocaleString()} this week`} color="blue" />
        <StatCard icon={Activity} label="Active Sessions" value={stats?.active_sessions} color="green" />
        <StatCard icon={Shield} label="Unack. Alerts" value={stats?.unacknowledged_alerts} sub={`${stats?.high_risk_today} high-risk today`} color="red" />
        <StatCard icon={Server} label="Servers Online" value={`${stats?.online_servers}/${stats?.total_servers}`} color="purple" />
      </div>

      {/* Activity chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white">Command Activity</h2>
          <div className="flex gap-1">
            {['24h', '7d', '30d'].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`text-xs px-3 py-1 rounded-md transition-colors ${
                  period === p ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chart || []}>
            <defs>
              <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} />
            <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
            <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }} />
            <Area type="monotone" dataKey="total" stroke="#3b82f6" fill="url(#totalGrad)" name="Total" strokeWidth={2} />
            <Area type="monotone" dataKey="high_risk" stroke="#ef4444" fill="url(#riskGrad)" name="High Risk" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top users */}
        <div className="card">
          <h2 className="text-sm font-semibold text-white mb-3">Top Active Users</h2>
          <div className="space-y-2">
            {(stats?.top_users || []).map((u, i) => (
              <div key={u.username} className="flex items-center gap-2">
                <span className="text-xs text-gray-600 w-4">{i + 1}</span>
                <span className="flex-1 text-sm text-gray-300 font-mono truncate">{u.username}</span>
                <span className="text-xs text-blue-400 font-medium">{u.count.toLocaleString()}</span>
              </div>
            ))}
            {!stats?.top_users?.length && <p className="text-xs text-gray-600">No data today</p>}
          </div>
        </div>

        {/* Top IPs */}
        <div className="card">
          <h2 className="text-sm font-semibold text-white mb-3">Top Source IPs</h2>
          <div className="space-y-2">
            {(stats?.top_ips || []).map((item, i) => (
              <div key={item.ip} className="flex items-center gap-2">
                <span className="text-xs text-gray-600 w-4">{i + 1}</span>
                <span className="flex-1 text-sm text-gray-300 font-mono">{item.ip}</span>
                <span className="text-xs text-blue-400 font-medium">{item.count.toLocaleString()}</span>
              </div>
            ))}
            {!stats?.top_ips?.length && <p className="text-xs text-gray-600">No data today</p>}
          </div>
        </div>

        {/* Risk distribution */}
        <div className="card">
          <h2 className="text-sm font-semibold text-white mb-3">Risk Distribution (7d)</h2>
          {riskDist?.length ? (
            <ResponsiveContainer width="100%" height={140}>
              <PieChart>
                <Pie data={riskDist} dataKey="count" nameKey="risk_level" cx="50%" cy="50%" outerRadius={55} label={({ risk_level, percent }) => `${risk_level} ${(percent * 100).toFixed(0)}%`} labelLine={false} fontSize={10}>
                  {(riskDist || []).map((entry) => (
                    <Cell key={entry.risk_level} fill={RISK_COLORS[entry.risk_level] || '#6b7280'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-xs text-gray-600">No data</p>}
        </div>
      </div>

      {/* Recent commands */}
      <div className="card">
        <h2 className="text-sm font-semibold text-white mb-3">Recent Commands</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 pr-4">Time ({TIMEZONE_LABEL})</th>
                <th className="text-left py-2 pr-4">Server</th>
                <th className="text-left py-2 pr-4">User</th>
                <th className="text-left py-2 pr-4">Remote IP</th>
                <th className="text-left py-2 pr-4">Command</th>
                <th className="text-left py-2">Risk</th>
              </tr>
            </thead>
            <tbody>
              {(stats?.recent_commands || []).map((cmd) => (
                <tr key={cmd.id} className="table-row-hover border-b border-gray-800/50">
                  <td className="py-2 pr-4 text-gray-500 whitespace-nowrap font-mono">
                    {formatTime(cmd.timestamp)}
                  </td>
                  <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">{cmd.server_name}</td>
                  <td className="py-2 pr-4 text-blue-400 font-mono whitespace-nowrap">{cmd.username}</td>
                  <td className="py-2 pr-4 text-gray-500 font-mono whitespace-nowrap">{cmd.remote_ip || '—'}</td>
                  <td className="py-2 pr-4 text-gray-300 font-mono max-w-xs truncate">{cmd.command}</td>
                  <td className="py-2"><RiskBadge level={cmd.risk_level} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!stats?.recent_commands?.length && <p className="text-xs text-gray-600 py-4 text-center">No commands yet</p>}
        </div>
      </div>
    </div>
  )
}
