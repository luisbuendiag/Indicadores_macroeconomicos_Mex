// La publicación se vigila por hora de consulta, nunca por mes del indicador.

// Fecha y hora de pared en una zona horaria, para un instante dado.
function wallClock(ms, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {timeZone, hourCycle: 'h23',
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'})
    .formatToParts(new Date(ms));
  const v = Object.fromEntries(parts.map(p => [p.type, Number(p.value)]));
  return {y: v.year, m: v.month, d: v.day, ms: Date.UTC(v.year, v.month - 1, v.day, v.hour, v.minute, v.second)};
}

// Instante UTC de una hora local (y, m, d, h, mi) en la zona indicada.
function zonedToUtc(y, m, d, h, mi, timeZone) {
  const guess = Date.UTC(y, m - 1, d, h, mi);
  let utc = guess - (wallClock(guess, timeZone).ms - guess);
  const second = guess - (wallClock(utc, timeZone).ms - utc);
  if (second !== utc) utc = second;  // cambio de horario
  return new Date(utc);
}

// Último corte vencido: el mismo criterio que latest_slot() en release_control.py
// (horas locales de config/update_policy.json, solo lunes a viernes locales),
// recorrido por los minutos de gracia.
export function expectedSlot(policy, now = new Date()) {
  const cutoff = new Date(now.getTime() - policy.grace_minutes * 60000);
  if (policy.timezone && policy.local_weekday_times?.length) {
    const times = policy.local_weekday_times.map(t => t.split(':').map(Number))
      .sort((a, b) => (b[0] * 60 + b[1]) - (a[0] * 60 + a[1]));
    const today = wallClock(cutoff.getTime(), policy.timezone);
    for (let day = 0; day < 8; day++) {
      const date = new Date(Date.UTC(today.y, today.m - 1, today.d - day));
      const weekday = date.getUTCDay();
      if (weekday === 0 || weekday === 6) continue;
      for (const [hour, minute] of times) {
        const slot = zonedToUtc(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate(), hour, minute, policy.timezone);
        if (slot <= cutoff) return slot;
      }
    }
    throw new Error('No se pudo determinar el corte de actualización');
  }
  // Formato anterior: horas UTC con un mismo minuto.
  const weekday = new Intl.DateTimeFormat('en-US', {timeZone: policy.timezone || 'UTC', weekday: 'short'});
  for (let day = 0; day < 8; day++) {
    const date = new Date(cutoff);
    date.setUTCDate(date.getUTCDate() - day);
    for (const hour of [...policy.utc_hours].sort((a, b) => b - a)) {
      const slot = new Date(date);
      slot.setUTCHours(hour, policy.minute, 0, 0);
      // Midnight UTC belongs to the previous local day in Mexico City.
      if (['Sat', 'Sun'].includes(weekday.format(slot))) continue;
      if (slot <= cutoff) return slot;
    }
  }
  throw new Error('No se pudo determinar el corte de actualización');
}

export function assessHealth(health, policy, now = new Date()) {
  if (policy.automatic_updates_enabled === false) {
    return {slot:null, stale:false, data:[], notes:[], recoverable:false,
      message:'Beta de consulta · Actualización automática aún no activada. Cada ficha indica su periodo de referencia.'};
  }
  const slot = expectedSlot(policy, now);
  const checked = new Date(health?.data_checked_at || '');
  const stale = !Number.isFinite(checked.getTime()) || checked < slot || checked > now;
  const data = health?.pending_data || [];
  const notes = health?.pending_notes || [];
  const parts = [];
  if (stale) parts.push('La actualización programada sigue pendiente.');
  if (data.length) parts.push(`Datos pendientes: ${data.join(', ')}.`);
  if (notes.length) parts.push(`Notas pendientes: ${notes.join(', ')}.`);
  if (health?.data_error && !stale) parts.push('La última consulta no superó la validación.');
  return {slot: slot.toISOString(), stale, data, notes, message: parts.join(' '),
    recoverable: stale || data.length > 0 || Boolean(health?.data_error)};
}
