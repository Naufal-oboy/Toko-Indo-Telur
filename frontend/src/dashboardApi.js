const api = '/api/dashboard'
const queueKey = 'indo-telur-receipt-queue-v1'

export async function dashboardRequest(path = '', method = 'GET', body, signal) {
  let response
  try {
    response = await fetch(api + path, {
      method,
      signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw Object.assign(new Error('Server tidak dapat dijangkau.'), { offline: true })
  }
  const content = await response.json().catch(() => null)
  if (!response.ok || !content?.success) {
    throw Object.assign(new Error(content?.message || 'Server belum siap. Coba lagi.'), {
      offline: response.status >= 500,
    })
  }
  return content.data
}

export function readReceiptQueue() {
  try {
    const entries = JSON.parse(localStorage.getItem(queueKey) || '[]')
    return Array.isArray(entries) ? entries : []
  } catch {
    return []
  }
}

export function saveReceiptQueue(entries) {
  try {
    localStorage.setItem(queueKey, JSON.stringify(entries))
  } catch {
    throw new Error('Penyimpanan browser tidak tersedia untuk antrean nota.')
  }
}
