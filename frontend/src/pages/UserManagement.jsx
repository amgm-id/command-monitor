import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi } from '../services/api'
import { formatDate, formatDateTimeShort } from '../utils/datetime'
import { Plus, UserCog, Pencil, UserX } from 'lucide-react'
import clsx from 'clsx'

const ROLES = ['super_admin', 'admin', 'auditor', 'viewer']
const ROLE_COLORS = {
  super_admin: 'bg-purple-950 text-purple-400 border-purple-800',
  admin: 'bg-blue-950 text-blue-400 border-blue-800',
  auditor: 'bg-yellow-950 text-yellow-400 border-yellow-800',
  viewer: 'bg-gray-800 text-gray-400 border-gray-700',
}

function UserModal({ user, onClose, onSave }) {
  const isEdit = !!user
  const [form, setForm] = useState({
    username: user?.username || '',
    email: user?.email || '',
    full_name: user?.full_name || '',
    role: user?.role || 'viewer',
    password: '',
    is_active: user?.is_active ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const data = { ...form }
      if (!data.password) delete data.password
      await onSave(data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save user')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md">
        <div className="p-5 border-b border-gray-800">
          <h2 className="text-base font-semibold text-white">{isEdit ? 'Edit User' : 'Add User'}</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && <p className="text-sm text-red-400 bg-red-950/30 border border-red-800/50 rounded px-3 py-2">{error}</p>}
          {!isEdit && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username</label>
              <input className="input" placeholder="johndoe" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            </div>
          )}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Email</label>
            <input type="email" className="input" placeholder="john@example.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Full Name</label>
            <input className="input" placeholder="John Doe" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Role</label>
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLES.map((r) => <option key={r} value={r}>{r.replace('_', ' ').toUpperCase()}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">{isEdit ? 'New Password (leave blank to keep current)' : 'Password'}</label>
            <input type="password" className="input" placeholder="••••••••" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} required={!isEdit} />
          </div>
          {isEdit && (
            <div className="flex items-center gap-3">
              <input type="checkbox" id="is_active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <label htmlFor="is_active" className="text-sm text-gray-400">Active account</label>
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary flex-1">{saving ? 'Saving...' : 'Save'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function UserManagement() {
  const [modalUser, setModalUser] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const qc = useQueryClient()

  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.list().then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => qc.invalidateQueries(['users']),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => usersApi.update(id, data),
    onSuccess: () => qc.invalidateQueries(['users']),
  })

  const deleteMutation = useMutation({
    mutationFn: usersApi.delete,
    onSuccess: () => qc.invalidateQueries(['users']),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">User Management</h1>
          <p className="text-sm text-gray-500 mt-0.5">{users?.length || 0} users</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2 text-sm">
          <Plus size={14} /> Add User
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800/50">
            <tr className="text-gray-500 border-b border-gray-800 text-xs">
              {['Username', 'Full Name', 'Email', 'Role', 'Status', 'Last Login', 'Created', 'Actions'].map((h) => (
                <th key={h} className="text-left px-5 py-3 font-medium whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={8} className="text-center py-10 text-gray-500">Loading...</td></tr>
            ) : (users || []).map((u) => (
              <tr key={u.id} className="table-row-hover border-b border-gray-800/40 text-xs">
                <td className="px-5 py-3 font-mono text-white">{u.username}</td>
                <td className="px-5 py-3 text-gray-300">{u.full_name || '—'}</td>
                <td className="px-5 py-3 text-gray-400">{u.email}</td>
                <td className="px-5 py-3">
                  <span className={clsx('badge', ROLE_COLORS[u.role])}>{u.role.replace('_', ' ').toUpperCase()}</span>
                </td>
                <td className="px-5 py-3">
                  <span className={`badge ${u.is_active ? 'bg-green-950 text-green-400 border-green-800' : 'bg-gray-800 text-gray-500 border-gray-700'}`}>
                    {u.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-5 py-3 text-gray-500 font-mono">
                  {u.last_login ? formatDateTimeShort(u.last_login) : '—'}
                </td>
                <td className="px-5 py-3 text-gray-500 font-mono">
                  {formatDate(u.created_at)}
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <button onClick={() => setModalUser(u)} className="text-blue-400 hover:text-blue-300">
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => {
                      if (confirm(`Deactivate ${u.username}?`)) deleteMutation.mutate(u.id)
                    }} className="text-red-400 hover:text-red-300">
                      <UserX size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showAdd && (
        <UserModal
          onClose={() => setShowAdd(false)}
          onSave={createMutation.mutateAsync}
        />
      )}
      {modalUser && (
        <UserModal
          user={modalUser}
          onClose={() => setModalUser(null)}
          onSave={(data) => updateMutation.mutateAsync({ id: modalUser.id, data })}
        />
      )}
    </div>
  )
}
