// La publicación se vigila por hora de consulta, nunca por mes del indicador.
export function expectedSlot(policy, now = new Date()) {
  const cutoff = new Date(now.getTime() - policy.grace_minutes * 60000);
  for (let day = 0; day < 8; day++) {
    const date = new Date(cutoff);
    date.setUTCDate(date.getUTCDate() - day);
    if ([0, 6].includes(date.getUTCDay())) continue;
    for (const hour of [...policy.utc_hours].sort((a, b) => b - a)) {
      const slot = new Date(date);
      slot.setUTCHours(hour, policy.minute, 0, 0);
      if (slot <= cutoff) return slot;
    }
  }
  throw new Error('No se pudo determinar el corte de actualización');
}

export function assessHealth(health, policy, now = new Date()) {
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
