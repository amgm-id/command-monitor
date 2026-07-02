import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sessionsApi, serversApi } from '../services/api'
import { formatTime, formatRelative } from '../utils/datetime'
import { Activity, RefreshCw, Monitor, User, Globe, Clock, XCircle, AlertTriangle } from 'lucide-react'
import { useState } from 'react'

function KillConfirmModal({ session, onConfirm, onCancel, loading }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-sm mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center flex-shrink-0">
            <AlertTriangle size={18} className="text-red-400" />
          </div>
          <div>
            <h3 className="text-white font-semibold">Hentikan Sesi</h3>
            <p className="text-xs text-gray-500">Tindakan ini tidak bisa dibatalkan</p>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-3 mb-5 space-y-1.5 text-xs font-mono">
          <div className="flex gap-2">
            <span className="text-gray-500 w-20">User</span>
            <span className="text-blue-400">{session.username}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-500 w-20">Server</span>
            <span className="text-gray-300">{session.server_name}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-500 w-20">Terminal</span>
            <span className="text-gray-300">{session.terminal || '—'}</span>
          </div>
          {session.remote_ip && (
            <div className="flex gap-2">
              <span className="text-gray-500 w-20">Remote IP</span>
              <span className="text-gray-300">{session.remote_ip}</span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 btn-secondary text-sm"
          >
            Batal
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <XCircle size={14} />
            )}
            Hentikan Sesi
          </button>
        </div>
      </div>
    </div>
  )
}

function KillResultToast({ result, onClose }) {
  const ok = result?.success
  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl border text-sm font-medium
      ${ok ? 'bg-green-900/90 border-green-600/40 text-green-300' : 'bg-red-900/90 border-red-600/40 text-red-300'}`}>
      {ok ? <Activity size={15} /> : <AlertTriangle size={15} />}
      <span>{result?.message}</span>
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100 text-xs">✕</button>
    </div>
  )
}

export default function ActiveSessions() {
  const [serverId, setServerId] = useState('')
  const [username, setUsername] = useState('')
  const [killing, setKilling] = useState(null)   // session yang dikonfirmasi untuk kill
  const [toast, setToast] = useState(null)
  const qc = useQueryClient()

  const { data: servers } = useQuery({
    queryKey: ['servers'],
    queryFn: () => serversApi.list().then((r) => r.data),
  })

  const { data: sessions, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['active-sessions', serverId, username],
    queryFn: () => sessionsApi.active({ server_id: serverId || undefined, username: username || undefined }).then((r) => r.data),
    refetchInterval: 15_000,
  })

  const killMutation = useMutation({
    mutationFn: (session) => sessionsApi.killSession({
      server_id: session.server_id,
      terminal: session.terminal,
      pid: session.pid || null,
      username: session.username,
    }),
    onSuccess: async (res) => {
      const actionId = res.data?.action_id
      setKilling(null)

      // Poll status aksi hingga selesai (maks 30 detik)
      let attempts = 0
      const maxAttempts = 10
      const poll = async () => {
        if (attempts++ >= maxAttempts) {
          setToast({ success: false, message: 'Timeout — periksa status manual' })
          return
        }
        try {
          const r = await sessionsApi.actionStatus(actionId)
          const { status, result } = r.data
          if (status === 'done') {
            setToast({ success: true, message: result || 'Sesi berhasil dihentikan' })
            qc.invalidateQueries({ queryKey: ['active-sessions'] })
            setTimeout(() => setToast(null), 5000)
          } else if (status === 'failed') {
            setToast({ success: false, message: result || 'Gagal menghentikan sesi' })
            setTimeout(() => setToast(null), 6000)
          } else {
            setTimeout(poll, 3000)
          }
        } catch {
          setTimeout(poll, 3000)
        }
      }
      setTimeout(poll, 2000)
    },
    onError: () => {
      setKilling(null)
      setToast({ success: false, message: 'Gagal mengirim perintah ke server' })
      setTimeout(() => setToast(null), 5000)
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Active Sessions</h1>
          <p className="text-sm text-gray-500 mt-0.5">{sessions?.length || 0} active sessions</p>
        </div>
        <button onClick={() => refetch()} disabled={isFetching} className="btn-secondary flex items-center gap-2 text-sm">
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="flex gap-3">
        <select className="input text-sm max-w-xs" value={serverId} onChange={(e) => setServerId(e.target.value)}>
          <option value="">All Servers</option>
          {(servers || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <input className="input text-sm max-w-xs" placeholder="Filter by username..." value={username} onChange={(e) => setUsername(e.target.value)} />
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-40"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" /></div>
      ) : (sessions || []).length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16 text-gray-500">
          <Activity size={40} className="mb-3 opacity-30" />
          <p>No active sessions</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {(sessions || []).map((s) => (
            <div key={s.id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center justify-center">
                    <User size={18} className="text-green-400" />
                  </div>
                  <div>
                    <p className="font-semibold text-white font-mono">{s.username}</p>
                    <p className="text-xs text-gray-500">{s.server_name} — {s.terminal || 'unknown terminal'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1.5 text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2.5 py-1 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                    Active
                  </span>
                  <button
                    onClick={() => setKilling(s)}
                    className="flex items-center gap-1.5 text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2.5 py-1 rounded-full hover:bg-red-500/20 transition-colors"
                    title="Hentikan sesi ini"
                  >
                    <XCircle size={12} />
                    Kill
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-800">
                <div className="flex items-start gap-2">
                  <Globe size={13} className="text-gray-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider">Remote IP</p>
                    <p className="text-sm text-gray-300 font-mono">{s.remote_ip || 'console'}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Clock size={13} className="text-gray-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider">Login Time</p>
                    <p className="text-sm text-gray-300 font-mono">{formatTime(s.login_time)} <span className="text-[10px] text-gray-600">WITA</span></p>
                    <p className="text-[10px] text-gray-600">{formatRelative(s.login_time)}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Monitor size={13} className="text-gray-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider">Idle</p>
                    <p className="text-sm text-gray-300 font-mono">{s.idle_time || '0s'}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Activity size={13} className="text-gray-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider">Process</p>
                    <p className="text-sm text-gray-300 font-mono truncate max-w-[150px]" title={s.current_process}>
                      {s.current_process || '—'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {killing && (
        <KillConfirmModal
          session={killing}
          loading={killMutation.isPending}
          onConfirm={() => killMutation.mutate(killing)}
          onCancel={() => setKilling(null)}
        />
      )}

      {toast && <KillResultToast result={toast} onClose={() => setToast(null)} />}
    </div>
  )
}
