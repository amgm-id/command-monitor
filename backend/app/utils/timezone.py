"""Timezone utilities — seluruh server menggunakan Asia/Makassar (WITA).
Simpan dan tampilkan waktu lokal secara langsung tanpa konversi UTC."""
from datetime import datetime

WITA_LABEL = "WITA"


def now() -> datetime:
    """Waktu sekarang (waktu lokal server = WITA)."""
    return datetime.now()


# Alias untuk backward compat — semua router masih import nama-nama ini
utc_now = now
now_wita = now


def fmt_wita(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime ke string."""
    if dt is None:
        return ""
    return dt.strftime(fmt)


def fmt_wita_label(dt: datetime) -> str:
    """Format datetime dengan label WITA: '2026-07-01 10:30:00 WITA'."""
    if dt is None:
        return ""
    return f"{fmt_wita(dt)} {WITA_LABEL}"


def to_wita(dt: datetime) -> datetime:
    """No-op — data sudah dalam waktu lokal WITA."""
    return dt
