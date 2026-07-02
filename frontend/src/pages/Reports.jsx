import { useState } from 'react'
import { commandLogsApi, sessionsApi } from '../services/api'
import { FileBarChart, Download, Terminal, LogIn } from 'lucide-react'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default function Reports() {
  const [params, setParams] = useState({ date_from: '', date_to: '', username: '', server_id: '' })
  const [loading, setLoading] = useState({})

  const setParam = (k, v) => setParams((p) => ({ ...p, [k]: v }))

  const exportReport = async (type, fmt) => {
    const key = `${type}-${fmt}`
    setLoading((l) => ({ ...l, [key]: true }))
    try {
      const cleanParams = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== ''))
      let res
      if (type === 'commands') {
        res = await commandLogsApi.export(fmt, cleanParams)
        downloadBlob(res.data, `command_history_${new Date().toISOString().slice(0, 10)}.${fmt === 'excel' ? 'xlsx' : fmt}`)
      } else {
        res = await sessionsApi.exportHistory(fmt, cleanParams)
        downloadBlob(res.data, `login_history_${new Date().toISOString().slice(0, 10)}.${fmt === 'excel' ? 'xlsx' : fmt}`)
      }
    } catch (err) {
      alert('Export failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading((l) => ({ ...l, [key]: false }))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Reports & Export</h1>
        <p className="text-sm text-gray-500 mt-0.5">Export server activity data to CSV, Excel, or PDF</p>
      </div>

      {/* Filters */}
      <div className="card">
        <h2 className="text-sm font-semibold text-white mb-4">Report Filters</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Date From</label>
            <input type="datetime-local" className="input text-sm" value={params.date_from} onChange={(e) => setParam('date_from', e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Date To</label>
            <input type="datetime-local" className="input text-sm" value={params.date_to} onChange={(e) => setParam('date_to', e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Username</label>
            <input className="input text-sm" placeholder="Filter by user..." value={params.username} onChange={(e) => setParam('username', e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Server</label>
            <input className="input text-sm" placeholder="Server name..." value={params.server_id} onChange={(e) => setParam('server_id', e.target.value)} />
          </div>
        </div>
      </div>

      {/* Report types */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Command History Report */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-500/10 border border-blue-500/20 rounded-xl flex items-center justify-center">
              <Terminal size={18} className="text-blue-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Command History</h3>
              <p className="text-xs text-gray-500">All commands executed on servers</p>
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            Includes: timestamp, server, username, remote IP, terminal, working directory, command, exit code, risk level.
          </p>
          <div className="flex gap-2">
            {[['csv', 'CSV'], ['excel', 'Excel'], ['pdf', 'PDF']].map(([fmt, label]) => (
              <button
                key={fmt}
                onClick={() => exportReport('commands', fmt)}
                disabled={loading[`commands-${fmt}`]}
                className="btn-secondary flex-1 text-xs flex items-center justify-center gap-1.5"
              >
                <Download size={12} />
                {loading[`commands-${fmt}`] ? 'Exporting...' : label}
              </button>
            ))}
          </div>
        </div>

        {/* Login History Report */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-green-500/10 border border-green-500/20 rounded-xl flex items-center justify-center">
              <LogIn size={18} className="text-green-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Login History</h3>
              <p className="text-xs text-gray-500">All SSH and console session records</p>
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            Includes: server, username, remote IP, terminal, login/logout time, duration, method, status.
          </p>
          <div className="flex gap-2">
            {[['csv', 'CSV'], ['excel', 'Excel'], ['pdf', 'PDF']].map(([fmt, label]) => (
              <button
                key={fmt}
                onClick={() => exportReport('sessions', fmt)}
                disabled={loading[`sessions-${fmt}`]}
                className="btn-secondary flex-1 text-xs flex items-center justify-center gap-1.5"
              >
                <Download size={12} />
                {loading[`sessions-${fmt}`] ? 'Exporting...' : label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Notes */}
      <div className="card bg-blue-950/20 border-blue-800/30">
        <h3 className="text-sm font-semibold text-blue-300 mb-2">Export Notes</h3>
        <ul className="text-xs text-blue-400/70 space-y-1 list-disc list-inside">
          <li>Maximum 10,000 records per export</li>
          <li>Apply date filters to narrow the dataset before exporting</li>
          <li>CSV exports use UTF-8 BOM encoding for Excel compatibility</li>
          <li>PDF exports use landscape A4 format for better readability</li>
          <li>All timestamps are in UTC</li>
        </ul>
      </div>
    </div>
  )
}
