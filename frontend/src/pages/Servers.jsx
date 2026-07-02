import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { serversApi } from '../services/api'
import { Link } from 'react-router-dom'
import { Server, Plus, Circle, Copy, ChevronRight, Cpu, Terminal, Clock } from 'lucide-react'
import { differenceInMinutes } from 'date-fns'
import { formatRelative, parseUTC } from '../utils/datetime'
import clsx from 'clsx'

function AddServerModal({ onClose, onSave }) {
  const [form, setForm] = useState({ name: '', hostname: '', ip_address: '', description: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await onSave(form)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create server')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md">
        <div className="p-5 border-b border-gray-800">
          <h2 className="text-base font-semibold text-white">Add Server</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <p className="text-sm text-red-400 bg-red-950/30 border border-red-800/50 rounded px-3 py-2">{error}</p>
          )}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Server Name</label>
            <input className="input" placeholder="222.5-hrd" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Hostname</label>
            <input className="input" placeholder="hrd" value={form.hostname}
              onChange={(e) => setForm({ ...form, hostname: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">IP Address</label>
            <input className="input" placeholder="10.10.222.5" value={form.ip_address}
              onChange={(e) => setForm({ ...form, ip_address: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Description (optional)</label>
            <input className="input" placeholder="Production server" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary flex-1">
              {saving ? 'Adding...' : 'Add Server'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ServerCard({ server, onCopyToken, copied }) {
  const online = server.last_seen &&
    differenceInMinutes(new Date(), parseUTC(server.last_seen)) < 5

  return (
    <div className={clsx(
      'bg-gray-900 border rounded-xl flex flex-col transition-colors hover:border-gray-600',
      online ? 'border-gray-700' : 'border-gray-800'
    )}>
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className={clsx(
              'w-9 h-9 rounded-lg flex-shrink-0 flex items-center justify-center border',
              online
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-gray-800 border-gray-700'
            )}>
              <Server size={16} className={online ? 'text-green-400' : 'text-gray-500'} />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-white text-sm truncate">{server.name}</p>
              <p className="text-xs text-gray-500 font-mono truncate">{server.hostname}</p>
            </div>
          </div>
          <span className={clsx(
            'flex-shrink-0 flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border',
            online
              ? 'text-green-400 bg-green-500/10 border-green-500/20'
              : 'text-gray-500 bg-gray-800/60 border-gray-700'
          )}>
            <Circle size={5} className={online ? 'fill-green-400' : 'fill-gray-500'} />
            {online ? 'Online' : 'Offline'}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-px bg-gray-800/50 flex-1">
        <div className="bg-gray-900 p-3">
          <div className="flex items-center gap-1.5 text-gray-600 mb-1">
            <Terminal size={11} />
            <span className="text-[10px] uppercase tracking-wider">Commands</span>
          </div>
          <p className="text-sm font-semibold text-gray-200">
            {(server.total_commands || 0).toLocaleString()}
          </p>
        </div>
        <div className="bg-gray-900 p-3">
          <div className="flex items-center gap-1.5 text-gray-600 mb-1">
            <Clock size={11} />
            <span className="text-[10px] uppercase tracking-wider">Last Seen</span>
          </div>
          <p className="text-sm font-semibold text-gray-200 truncate">
            {server.last_seen ? formatRelative(server.last_seen) : 'Never'}
          </p>
        </div>
        <div className="bg-gray-900 p-3">
          <div className="flex items-center gap-1.5 text-gray-600 mb-1">
            <Cpu size={11} />
            <span className="text-[10px] uppercase tracking-wider">IP Address</span>
          </div>
          <p className="text-sm font-mono text-gray-200">{server.ip_address}</p>
        </div>
        <div className="bg-gray-900 p-3">
          <div className="flex items-center gap-1.5 text-gray-600 mb-1">
            <Server size={11} />
            <span className="text-[10px] uppercase tracking-wider">Version</span>
          </div>
          <p className="text-sm text-gray-200">{server.agent_version || '—'}</p>
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <code className="text-[11px] text-gray-600 font-mono truncate">
            {server.agent_token.slice(0, 24)}…
          </code>
          <button
            onClick={() => onCopyToken(server.agent_token, server.id)}
            className="flex-shrink-0 text-gray-600 hover:text-gray-300 transition-colors"
            title="Copy token"
          >
            {copied === server.id
              ? <span className="text-green-400 text-[10px] font-medium">Copied!</span>
              : <Copy size={12} />
            }
          </button>
        </div>
        <Link
          to={`/servers/${server.id}`}
          className="flex-shrink-0 flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
        >
          Detail <ChevronRight size={12} />
        </Link>
      </div>
    </div>
  )
}

export default function Servers() {
  const [showAdd, setShowAdd] = useState(false)
  const [copied, setCopied] = useState(null)
  const qc = useQueryClient()

  const { data: servers, isLoading } = useQuery({
    queryKey: ['servers'],
    queryFn: () => serversApi.list().then((r) => r.data),
    refetchInterval: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: serversApi.create,
    onSuccess: () => qc.invalidateQueries(['servers']),
  })

  const copyToken = (token, id) => {
    navigator.clipboard.writeText(token)
    setCopied(id)
    setTimeout(() => setCopied(null), 2000)
  }

  const online = (servers || []).filter((s) =>
    s.last_seen && differenceInMinutes(new Date(), parseUTC(s.last_seen)) < 5
  ).length

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Servers</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {servers?.length || 0} registered
            {online > 0 && (
              <span className="ml-2 text-green-400">· {online} online</span>
            )}
          </p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2 text-sm">
          <Plus size={14} /> Add Server
        </button>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
        </div>
      ) : (servers || []).length === 0 ? (
        <div className="card text-center py-20 text-gray-500">
          <Server size={40} className="mx-auto mb-3 opacity-20" />
          <p className="text-sm">No servers registered yet</p>
          <button onClick={() => setShowAdd(true)} className="btn-primary mt-4 text-sm">
            Add First Server
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {(servers || []).map((server) => (
            <ServerCard
              key={server.id}
              server={server}
              onCopyToken={copyToken}
              copied={copied}
            />
          ))}
        </div>
      )}

      {showAdd && (
        <AddServerModal onClose={() => setShowAdd(false)} onSave={createMutation.mutateAsync} />
      )}
    </div>
  )
}
