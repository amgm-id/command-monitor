import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { sessionsApi, serversApi } from '../services/api'
import { formatDateTime, formatTime, TIMEZONE_LABEL } from '../utils/datetime'
import { Download, Filter, X } from 'lucide-react'
import Pagination from '../components/Pagination'
import clsx from 'clsx'

const STATUS_STYLES = {
  active: 'bg-green-950 text-green-400 border-green-800',
  ended: 'bg-gray-800 text-gray-400 border-gray-700',
  failed: 'bg-red-950 text-red-400 border-red-800',
  timeout: 'bg-yellow-950 text-yellow-400 border-yellow-800',
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default function LoginHistory() {
  const [filters, setFilters] = useState({ username: '', remote_ip: '', server_id: '', status: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)

  const { data: servers } = useQuery({ queryKey: ['servers'], queryFn: () => serversApi.list().then((r) => r.data) })

  const queryParams = { ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')), page, per_page: 50 }

  const { data, isLoading } = useQuery({
    queryKey: ['session-history', queryParams],
    queryFn: () => sessionsApi.history(queryParams).then((r) => r.data),
    keepPreviousData: true,
  })

  const setFilter = (k, v) => { setFilters((f) => ({ ...f, [k]: v })); setPage(1) }

  const handleExport = async (fmt) => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
    const res = await sessionsApi.exportHistory(fmt, params)
    const exts = { csv: 'csv', excel: 'xlsx', pdf: 'pdf' }
    downloadBlob(res.data, `login_history.${exts[fmt]}`)
  }

  const formatDuration = (secs) => {
    if (!secs) return '—'
    const h = Math.floor(secs / 3600)
    const m = Math.floor((secs % 3600) / 60)
    const s = secs % 60
    return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Login History</h1>
          <p className="text-sm text-gray-500 mt-0.5">{data?.total?.toLocaleString() || 0} sessions</p>
        </div>
        <div className="flex gap-2">
          {['CSV', 'Excel', 'PDF'].map((f) => (
            <button key={f} onClick={() => handleExport(f.toLowerCase())} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
              <Download size={12} />{f}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <input className="input text-xs" placeholder="Username" value={filters.username} onChange={(e) => setFilter('username', e.target.value)} />
          <input className="input text-xs" placeholder="Remote IP" value={filters.remote_ip} onChange={(e) => setFilter('remote_ip', e.target.value)} />
          <select className="input text-xs" value={filters.server_id} onChange={(e) => setFilter('server_id', e.target.value)}>
            <option value="">All Servers</option>
            {(servers || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className="input text-xs" value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">All Status</option>
            {['active', 'ended', 'failed', 'timeout'].map((s) => <option key={s} value={s}>{s.toUpperCase()}</option>)}
          </select>
          <input type="datetime-local" className="input text-xs" value={filters.date_from} onChange={(e) => setFilter('date_from', e.target.value)} />
          <input type="datetime-local" className="input text-xs" value={filters.date_to} onChange={(e) => setFilter('date_to', e.target.value)} />
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-800/50">
              <tr className="text-gray-500 border-b border-gray-800">
                {['Server', 'Username', 'Remote IP', 'Terminal', `Login Time (${TIMEZONE_LABEL})`, `Logout Time (${TIMEZONE_LABEL})`, 'Duration', 'Method', 'Status'].map((h) => (
                  <th key={h} className="text-left px-4 py-3 font-medium whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={9} className="text-center py-10 text-gray-500">Loading...</td></tr>
              ) : (data?.items || []).length === 0 ? (
                <tr><td colSpan={9} className="text-center py-10 text-gray-500">No sessions found</td></tr>
              ) : (data?.items || []).map((s) => (
                <tr key={s.id} className="table-row-hover border-b border-gray-800/40">
                  <td className="px-4 py-2.5 text-gray-300 whitespace-nowrap">{s.server_name || '—'}</td>
                  <td className="px-4 py-2.5 text-blue-400 font-mono whitespace-nowrap">{s.username}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">{s.remote_ip || 'console'}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono">{s.terminal || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-400 font-mono whitespace-nowrap">
                    {formatDateTime(s.login_time)}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">
                    {s.logout_time ? formatTime(s.logout_time) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">{formatDuration(s.duration)}</td>
                  <td className="px-4 py-2.5 text-gray-500 uppercase font-mono">{s.login_method}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <span className={clsx('badge', STATUS_STYLES[s.status] || STATUS_STYLES.ended)}>{s.status.toUpperCase()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 border-t border-gray-800">
          <Pagination page={page} total={data?.total || 0} perPage={50} onChange={setPage} />
        </div>
      </div>
    </div>
  )
}
