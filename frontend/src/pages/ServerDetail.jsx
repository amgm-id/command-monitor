import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { serversApi, commandLogsApi } from '../services/api'
import { ArrowLeft, RefreshCw, RotateCcw, Copy } from 'lucide-react'
import { useState } from 'react'
import { differenceInMinutes } from 'date-fns'
import { formatDateTime, formatTime, parseUTC, TIMEZONE_LABEL } from '../utils/datetime'
import RiskBadge from '../components/RiskBadge'
import { dashboardApi } from '../services/api'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function ServerDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [copied, setCopied] = useState(false)

  const { data: server, isLoading } = useQuery({
    queryKey: ['server', id],
    queryFn: () => serversApi.get(id).then((r) => r.data),
  })

  const { data: recentCmds } = useQuery({
    queryKey: ['server-commands', id],
    queryFn: () => commandLogsApi.list({ server_id: id, per_page: 20, page: 1 }).then((r) => r.data),
    refetchInterval: 15_000,
  })

  const { data: chart } = useQuery({
    queryKey: ['activity-chart', '24h', id],
    queryFn: () => dashboardApi.activityChart('24h', id).then((r) => r.data),
    refetchInterval: 60_000,
  })

  const rotateMutation = useMutation({
    mutationFn: () => serversApi.rotateToken(id),
    onSuccess: () => qc.invalidateQueries(['server', id]),
  })

  if (isLoading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" /></div>
  if (!server) return <div className="text-gray-500">Server not found</div>

  const isOnline = server.last_seen && differenceInMinutes(new Date(), parseUTC(server.last_seen)) < 5

  const copyToken = () => {
    navigator.clipboard.writeText(server.agent_token)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/servers" className="text-gray-500 hover:text-gray-300"><ArrowLeft size={18} /></Link>
        <div>
          <h1 className="text-xl font-bold text-white">{server.name}</h1>
          <p className="text-sm text-gray-500 font-mono mt-0.5">{server.hostname} — {server.ip_address}</p>
        </div>
        <span className={`ml-auto flex items-center gap-1.5 text-xs px-3 py-1 rounded-full border ${isOnline ? 'text-green-400 bg-green-500/10 border-green-500/20' : 'text-gray-500 bg-gray-800 border-gray-700'}`}>
          <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
          {isOnline ? 'Online' : 'Offline'}
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Commands', value: server.total_commands?.toLocaleString() || '0' },
          { label: `Last Seen (${TIMEZONE_LABEL})`, value: server.last_seen ? formatTime(server.last_seen) : 'Never' },
          { label: 'Agent Version', value: server.agent_version || '—' },
          { label: 'OS', value: server.os_info?.pretty_name || server.os_info?.id || '—' },
        ].map((item) => (
          <div key={item.label} className="card">
            <p className="text-xs text-gray-500">{item.label}</p>
            <p className="text-xl font-bold text-white mt-1">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Agent Token */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white">Agent Token</h2>
          <button onClick={() => rotateMutation.mutate()} disabled={rotateMutation.isPending}
            className="btn-secondary text-xs flex items-center gap-1.5">
            <RotateCcw size={12} className={rotateMutation.isPending ? 'animate-spin' : ''} />
            Rotate Token
          </button>
        </div>
        <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3">
          <code className="text-green-400 font-mono text-sm flex-1 break-all">{server.agent_token}</code>
          <button onClick={copyToken} className="text-gray-500 hover:text-gray-300 flex-shrink-0">
            {copied ? <span className="text-green-400 text-xs">Copied!</span> : <Copy size={14} />}
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-2">Use this token in the agent's config.yaml on this server.</p>
      </div>

      {/* Activity chart */}
      <div className="card">
        <h2 className="text-sm font-semibold text-white mb-4">Command Activity (24h)</h2>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={chart || []}>
            <defs>
              <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} />
            <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
            <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', fontSize: 12 }} />
            <Area type="monotone" dataKey="total" stroke="#3b82f6" fill="url(#grad)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Recent commands */}
      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-white">Recent Commands</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-800/50">
              <tr className="text-gray-500 border-b border-gray-800">
                {[`Time (${TIMEZONE_LABEL})`, 'Username', 'Remote IP', 'Command', 'Exit', 'Risk'].map((h) => (
                  <th key={h} className="text-left px-4 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(recentCmds?.items || []).map((cmd) => (
                <tr key={cmd.id} className="table-row-hover border-b border-gray-800/40">
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">
                    {formatTime(cmd.timestamp)}
                  </td>
                  <td className="px-4 py-2.5 text-blue-400 font-mono">{cmd.username}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono">{cmd.remote_ip || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-200 font-mono max-w-[250px]">
                    <span className="block truncate" title={cmd.command}>{cmd.command}</span>
                  </td>
                  <td className="px-4 py-2.5 font-mono">
                    {cmd.exit_code != null ? (
                      <span className={cmd.exit_code === 0 ? 'text-green-400' : 'text-red-400'}>{cmd.exit_code}</span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2.5"><RiskBadge level={cmd.risk_level} /></td>
                </tr>
              ))}
              {!recentCmds?.items?.length && (
                <tr><td colSpan={6} className="text-center py-8 text-gray-500">No commands yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
