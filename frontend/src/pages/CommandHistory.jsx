import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { commandLogsApi, serversApi } from '../services/api'
import { onWsEvent } from '../services/websocket'
import { formatDateTime, TIMEZONE_LABEL } from '../utils/datetime'
import { Search, Download, Filter, X } from 'lucide-react'
import RiskBadge from '../components/RiskBadge'
import Pagination from '../components/Pagination'

const RISK_LEVELS = ['', 'low', 'medium', 'high', 'critical']

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function CommandHistory() {
  const [filters, setFilters] = useState({
    username: '', remote_ip: '', command: '', server_id: '',
    risk_level: '', date_from: '', date_to: '',
  })
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)

  const queryClient = useQueryClient()

  // Auto-refresh table when new commands arrive
  useEffect(() => {
    const unsub = onWsEvent('new_commands', () => {
      queryClient.invalidateQueries({ queryKey: ['command-logs'] })
    })
    return unsub
  }, [queryClient])

  const { data: servers } = useQuery({
    queryKey: ['servers'],
    queryFn: () => serversApi.list().then((r) => r.data),
  })

  const queryParams = {
    ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
    page,
    per_page: 50,
  }

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['command-logs', queryParams],
    queryFn: () => commandLogsApi.list(queryParams).then((r) => r.data),
    keepPreviousData: true,
  })

  const handleFilterChange = (k, v) => {
    setFilters((f) => ({ ...f, [k]: v }))
    setPage(1)
  }

  const clearFilters = () => {
    setFilters({ username: '', remote_ip: '', command: '', server_id: '', risk_level: '', date_from: '', date_to: '' })
    setPage(1)
  }

  const handleExport = async (fmt) => {
    setExporting(true)
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
      const res = await commandLogsApi.export(fmt, params)
      const exts = { csv: 'csv', excel: 'xlsx', pdf: 'pdf' }
      downloadBlob(res.data, `command_history.${exts[fmt]}`)
    } finally {
      setExporting(false)
    }
  }

  const hasFilters = Object.values(filters).some(Boolean)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Command History</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {data?.total?.toLocaleString() || 0} commands total
          </p>
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <button className="btn-secondary flex items-center gap-2 text-sm">
              <Download size={14} />
              Export
            </button>
            <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg py-1 z-10 min-w-[120px] hidden group-hover:block">
              {['csv', 'excel', 'pdf'].map((f) => (
                <button key={f} onClick={() => handleExport(f)} className="w-full text-left px-4 py-1.5 text-sm text-gray-300 hover:bg-gray-700 uppercase">
                  {f}
                </button>
              ))}
            </div>
          </div>
          {/* Inline export buttons */}
          {['CSV', 'Excel', 'PDF'].map((f) => (
            <button key={f} onClick={() => handleExport(f.toLowerCase())} disabled={exporting}
              className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
              <Download size={12} />
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={14} className="text-gray-500" />
          <span className="text-sm font-medium text-gray-400">Filters</span>
          {hasFilters && (
            <button onClick={clearFilters} className="ml-auto flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300">
              <X size={12} /> Clear all
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <input className="input text-xs" placeholder="Username" value={filters.username} onChange={(e) => handleFilterChange('username', e.target.value)} />
          <input className="input text-xs" placeholder="Remote IP" value={filters.remote_ip} onChange={(e) => handleFilterChange('remote_ip', e.target.value)} />
          <input className="input text-xs" placeholder="Command contains..." value={filters.command} onChange={(e) => handleFilterChange('command', e.target.value)} />
          <select className="input text-xs" value={filters.server_id} onChange={(e) => handleFilterChange('server_id', e.target.value)}>
            <option value="">All Servers</option>
            {(servers || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className="input text-xs" value={filters.risk_level} onChange={(e) => handleFilterChange('risk_level', e.target.value)}>
            <option value="">All Risk Levels</option>
            {['critical', 'high', 'medium', 'low'].map((r) => <option key={r} value={r}>{r.toUpperCase()}</option>)}
          </select>
          <input type="datetime-local" className="input text-xs" value={filters.date_from} onChange={(e) => handleFilterChange('date_from', e.target.value)} />
          <input type="datetime-local" className="input text-xs" value={filters.date_to} onChange={(e) => handleFilterChange('date_to', e.target.value)} />
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-800/50">
              <tr className="text-gray-500 border-b border-gray-800">
                {[`Time (${TIMEZONE_LABEL})`, 'Server', 'IP Server', 'Username', 'Remote IP', 'Terminal', 'Working Dir', 'Command', 'Status', 'Risk'].map((h) => (
                  <th key={h} className="text-left px-4 py-3 font-medium whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={10} className="text-center py-12 text-gray-500">Loading...</td></tr>
              ) : (data?.items || []).length === 0 ? (
                <tr><td colSpan={10} className="text-center py-12 text-gray-500">No commands found</td></tr>
              ) : (data?.items || []).map((cmd) => (
                <tr key={cmd.id} className="table-row-hover border-b border-gray-800/40">
                  <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap font-mono">
                    {formatDateTime(cmd.timestamp)}
                  </td>
                  <td className="px-4 py-2.5 text-gray-300 whitespace-nowrap">{cmd.server_name || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">{cmd.server_ip || '—'}</td>
                  <td className="px-4 py-2.5 text-blue-400 font-mono whitespace-nowrap">{cmd.username}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">{cmd.remote_ip || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">{cmd.terminal || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono max-w-[120px] truncate" title={cmd.working_dir}>{cmd.working_dir || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-200 font-mono max-w-[200px]">
                    <span className="block truncate" title={cmd.command}>{cmd.command}</span>
                    {cmd.risk_reason && <span className="text-[10px] text-orange-400 block">{cmd.risk_reason}</span>}
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    {cmd.exit_code !== null && cmd.exit_code !== undefined ? (
                      <span className={`font-mono text-[10px] ${cmd.exit_code === 0 ? 'text-green-400' : 'text-red-400'}`}>
                        exit:{cmd.exit_code}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap"><RiskBadge level={cmd.risk_level} /></td>
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
