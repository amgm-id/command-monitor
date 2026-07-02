/**
 * Datetime utilities — semua timestamp dari backend sudah dalam waktu lokal Asia/Makassar (WITA).
 * Tidak ada konversi timezone — tampilkan apa adanya.
 */
import { formatDistanceToNow } from 'date-fns'

export const TIMEZONE = 'Asia/Makassar'
export const TIMEZONE_LABEL = 'WITA'

/**
 * Parse string datetime dari backend (format: 'YYYY-MM-DDTHH:MM:SS' atau 'YYYY-MM-DD HH:MM:SS').
 * Backend menyimpan waktu lokal WITA — tidak perlu konversi, buat Date sebagai local time.
 */
function parseLocal(dateStr) {
  if (!dateStr) return null
  const str = String(dateStr).replace(' ', 'T').replace('Z', '').split('+')[0]
  const d = new Date(str)
  return isNaN(d.getTime()) ? null : d
}

/** Alias untuk kompatibilitas dengan komponen yang menggunakan parseUTC */
export function parseUTC(dateStr) {
  return parseLocal(dateStr)
}

/** Format: "2024-06-30 17:30:45" */
export function formatDateTime(dateStr) {
  if (!dateStr) return '—'
  const s = String(dateStr).replace('T', ' ').split('+')[0].replace('Z', '')
  return s.length >= 19 ? s.substring(0, 19) : s
}

/** Format: "2024-06-30" */
export function formatDate(dateStr) {
  if (!dateStr) return '—'
  return String(dateStr).substring(0, 10)
}

/** Format: "17:30:45" */
export function formatTime(dateStr) {
  if (!dateStr) return '—'
  const s = String(dateStr).replace('T', ' ').split('+')[0].replace('Z', '')
  return s.length >= 19 ? s.substring(11, 19) : s.substring(11)
}

/** Format: "2024-06-30 17:30" (tanpa detik) */
export function formatDateTimeShort(dateStr) {
  if (!dateStr) return '—'
  const s = String(dateStr).replace('T', ' ').split('+')[0].replace('Z', '')
  return s.length >= 16 ? s.substring(0, 16) : s
}

/** Format relatif: "5 minutes ago", "2 hours ago", dll. */
export function formatRelative(dateStr) {
  const d = parseLocal(dateStr)
  if (!d || isNaN(d.getTime())) return '—'
  return formatDistanceToNow(d, { addSuffix: true })
}
