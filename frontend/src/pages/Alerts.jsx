import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi, serversApi } from '../services/api'
import { formatDateTime, TIMEZONE_LABEL } from '../utils/datetime'
import { Shield, CheckCheck, Filter } from 'lucide-react'
import RiskBadge from '../components/RiskBadge'
import Pagination from '../components/Pagination'

export default function Alerts() {
  const [filters, setFilters] = useState({ server_id: '', risk_level: '', is_acknowledged: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(new Set())
  const queryClient = useQueryClient()

  const { data: servers } = useQuery({ queryKey: ['servers'], queryFn: () => serversApi.list().then((r) => r.data) })

  const queryParams = {
    ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
    page, per_page: 50,
  }
  if (filters.is_acknowledged !== '') queryParams.is_acknowledged = filters.is_acknowledged === 'true'

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['alerts', queryParams],
    queryFn: () => alertsApi.list(queryParams).then((r) => r.data),
    keepPreviousData: true,
  })

  const ackMutation = useMutation({
    mutationFn: (id) => alertsApi.acknowledge(id, ''),
    onSuccess: () => { queryClient.invalidateQueries(['alerts']); queryClient.invalidateQueries(['alert-count']) },
  })

  const bulkAckMutation = useMutation({
    mutationFn: (ids) => alertsApi.acknowledgeBulk(ids),
    onSuccess: () => { setSelected(new Set()); queryClient.invalidateQueries(['alerts']); queryClient.invalidateQueries(['alert-count']) },
  })

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const setFilter = (k, v) => { setFilters((f) => ({ ...f, [k]: v })); setPage(1) }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Risk Alerts</h1>
          <p className="text-sm text-gray-500 mt-0.5">{data?.total?.toLocaleString() || 0} alerts</p>
        </div>
        {selected.size > 0 && (
          <button
            onClick={() => bulkAckMutation.mutate([...selected])}
            disabled={bulkAckMutation.isPending}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <CheckCheck size={14} />
            Acknowledge {selected.size} selected
          </button>
        )}
      </div>

      <div className="card">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <select className="input text-xs" value={filters.server_id} onChange={(e) => setFilter('server_id', e.target.value)}>
            <option value="">All Servers</option>
            {(servers || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className="input text-xs" value={filters.risk_level} onChange={(e) => setFilter('risk_level', e.target.value)}>
            <option value="">All Risk Levels</option>
            {['critical', 'high'].map((r) => <option key={r} value={r}>{r.toUpperCase()}</option>)}
          </select>
          <select className="input text-xs" value={filters.is_acknowledged} onChange={(e) => setFilter('is_acknowledged', e.target.value)}>
            <option value="">All Status</option>
            <option value="false">Unacknowledged</option>
            <option value="true">Acknowledged</option>
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
                <th className="px-4 py-3 w-8">
                  <input type="checkbox" className="rounded bg-gray-700 border-gray-600"
                    onChange={(e) => setSelected(e.target.checked ? new Set(data?.items?.map((a) => a.id)) : new Set())}
                    checked={selected.size === data?.items?.length && data?.items?.length > 0} />
                </th>
                {[`Time (${TIMEZONE_LABEL})`, 'Server', 'Username', 'Remote IP', 'Command', 'Risk', 'Reason', 'Status', 'Action'].map((h) => (
                  <th key={h} className="text-left px-4 py-3 font-medium whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={10} className="text-center py-10 text-gray-500">Loading...</td></tr>
              ) : (data?.items || []).length === 0 ? (
                <tr><td colSpan={10} className="text-center py-10 text-gray-500">
                  <Shield size={32} className="mx-auto mb-2 opacity-20" />
                  No alerts found
                </td></tr>
              ) : (data?.items || []).map((alert) => (
                <tr key={alert.id} className={`table-row-hover border-b border-gray-800/40 ${alert.is_acknowledged ? 'opacity-50' : ''}`}>
                  <td className="px-4 py-2.5">
                    <input type="checkbox" className="rounded bg-gray-700 border-gray-600"
                      checked={selected.has(alert.id)} onChange={() => toggleSelect(alert.id)} />
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">
                    {formatDateTime(alert.timestamp)}
                  </td>
                  <td className="px-4 py-2.5 text-gray-300 whitespace-nowrap">{alert.server_name || '—'}</td>
                  <td className="px-4 py-2.5 text-blue-400 font-mono whitespace-nowrap">{alert.username}</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">{alert.remote_ip || '—'}</td>
                  <td className="px-4 py-2.5 text-gray-200 font-mono max-w-[200px]">
                    <span className="block truncate" title={alert.command}>{alert.command}</span>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap"><RiskBadge level={alert.risk_level} /></td>
                  <td className="px-4 py-2.5 text-gray-500 max-w-[150px]">
                    <span className="block truncate" title={alert.risk_reason}>{alert.risk_reason || '—'}</span>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    {alert.is_acknowledged ? (
                      <span className="text-green-400 text-[10px]">✓ {alert.acknowledged_by}</span>
                    ) : (
                      <span className="text-yellow-400 text-[10px]">Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {!alert.is_acknowledged && (
                      <button
                        onClick={() => ackMutation.mutate(alert.id)}
                        disabled={ackMutation.isPending}
                        className="text-[10px] text-blue-400 hover:text-blue-300 bg-blue-950/50 px-2 py-1 rounded border border-blue-800/50 whitespace-nowrap"
                      >
                        Acknowledge
                      </button>
                    )}
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
