import { Fragment, useEffect, useRef, useState } from 'react'
import './ReceiptPage.css'
import { dashboardRequest, readReceiptQueue, saveReceiptQueue } from './dashboardApi.js'


const historyStatuses = {
  draft: 'Draft',
  ready: 'Siap',
  delivered: 'Diantar',
}

function historyDate(daysAgo = 0) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Makassar' }).format(new Date(Date.now() - daysAgo * 86400000))
}



const icons = {
  receipt: 'M5 3l2 1 2-1 3 1 3-1 2 1 2-1v18l-2-1-2 1-3-1-3 1-2-1-2 1z M8 8h8m-8 4h8m-8 4h5',
  history: 'M3 4v5h5 M3.5 9a9 9 0 1 1 0 6 M12 7v5l3 2',
  box: 'M3 7l9-5 9 5v10l-9 5-9-5z m0 0 9 5 9-5 M12 12v10 M7.5 4.5l9 5v4',
  shop: 'M3 9l3-6h12l3 6v2a3 3 0 0 1-5 2 3 3 0 0 1-4 0 3 3 0 0 1-4 0 3 3 0 0 1-5-2z M5 14v7h14v-7 M10 21v-5h4v5',
  archive: 'M3 4h18v5H3z M5 9v11h14V9 M10 13h4',
  sync: 'M21 3v6h-6 M3 21v-6h6 M20 9a8.5 8.5 0 0 0-15-3L3 9m1 6a8.5 8.5 0 0 0 15 3l2-3',
  exit: 'M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5 M9 12h12m-5-5 5 5-5 5',
  wifi: 'M2 8a16 16 0 0 1 20 0 M5 12a11 11 0 0 1 14 0 M8 16a6 6 0 0 1 8 0 M12 20h.01',
  person: 'M14 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M12 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M19 8v8m-4-4h8',
  arrow: 'M4 12h15m-7-7 7 7-7 7',
  check: 'm5 12 4 4L19 6',
  back: 'm15 6-6 6 6 6',
  search: 'M21 21l-5-5m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z',
  basket: 'M2 11h20M4 11l2 9h12l2-9M8 4l-4 7m12-7 4 7M9 12l1 8m5-8-1 8M5 15h14',
  trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
  download: 'M12 3v12m-5-5 5 5 5-5M3 15v5a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-5',
  syncOk: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z M7 12l3 3 6-6',
  syncPending: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z M12 7v6m0 4h.01',
  upload: 'M12 16V3m-5 5 5-5 5 5M3 15v5h18v-5',
  file: 'M5 2h9l5 5v15H5z M14 2v6h5 M12 18v-7m-3 3 3-3 3 3',
  shield: 'M12 2c2 2 5 3 8 3v6c0 5-3 8-8 11-5-3-8-6-8-11V5c3 0 6-1 8-3z M8 12l3 3 5-6',
  clock: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z M12 6v6l4 2',
  edit: 'm14 5 5 5M4 20l5-1L21 7a2 2 0 0 0-4-4L5 15z',
  info: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z M12 11v6m0-10h.01',
  plus: 'M12 5v14M5 12h14',
  oil: 'M9 19a7 7 0 0 0 12-5c0-4-5-7-7-12-1 2-2 4-4 6m-2-3c-2 4-5 6-5 9a4 4 0 0 0 8 0c0-3-2-5-3-9z',
  print: 'M6 8V3h12v5M6 17H3V8h18v9h-3M6 14h12v7H6zM7 11h.01',
  share: 'M9 10l6-4m-6 8 6 4M9 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM21 5a3 3 0 1 1-6 0 3 3 0 0 1 6 0zm0 14a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
  truck: 'M2 4h12v13H2zM14 8h4l4 5v4h-8M8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0zm12 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0z',
  egg: 'M12 2c4 0 8 7 8 12a8 8 0 1 1-16 0c0-5 4-12 8-12z',
  grain: 'M3 21 20 4M8 16c-4 0-5-3-2-6 3 0 4 3 2 6zm0 0c0 4 3 5 6 2 0-3-3-4-6-2zm5-5c-4 0-5-3-2-6 3 0 4 3 2 6zm0 0c0 4 3 5 6 2 0-3-3-4-6-2zm4-4c-1-3 1-5 5-5 0 4-2 6-5 5z',
}

const thousands = new Intl.NumberFormat('id-ID')
function money(amount) {
  return 'Rp ' + thousands.format(amount)
}

function Icon({ name }) {
  return (
    <svg className="nota-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={icons[name]} />
    </svg>
  )
}

function downloadFile(name, blob) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function exportReceipts(receipts) {
  const rows = [
    ['Nomor', 'Pelanggan', 'Alamat', 'Tanggal', 'Waktu', 'Total (Rp)', 'Status', 'Sinkron'],
    ...receipts.map((receipt) =>
      [receipt.number, receipt.customer.name, receipt.customer.area, receipt.date, receipt.time.replace('.', ':'), receipt.total, historyStatuses[receipt.status], syncLabel(receipt)],
    ),
  ]
  const csv = rows.map((row) => row.map((value) => {
    const field = String(value ?? '')
    const safeField = /^[\s]*[=+@-]|^[\t\r\n]/.test(field) ? "'" + field : field
    return '"' + safeField.replaceAll('"', '""') + '"'
  }).join(',')).join('\r\n')
  downloadFile('riwayat-nota.csv', new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' }))
}

const historyPeriods = [
  ['all', 'Semua waktu'],
  ['0', 'Hari ini'],
  ['6', '7 hari'],
  ['29', '30 hari'],
]

const shortHistoryDate = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Makassar' })
const longHistoryDate = new Intl.DateTimeFormat('id-ID', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Asia/Makassar' })

function ReceiptHistory({ receipts, openReceipt }) {
  const [query, setQuery] = useState('')
  const [date, setDate] = useState('')
  const [period, setPeriod] = useState('all')
  const [status, setStatus] = useState('all')
  const today = historyDate()
  const yesterday = historyDate(1)
  const earliest = period === 'all' ? '' : historyDate(Number(period))
  const search = query.trim().toLocaleLowerCase('id-ID')
  const matchingTime = receipts.filter((receipt) =>
    (receipt.number + ' ' + receipt.customer.name).toLocaleLowerCase('id-ID').includes(search) &&
    (date ? receipt.date === date : receipt.date >= earliest),
  )
  const visible = matchingTime.filter((receipt) => status === 'all' || receipt.status === status)
  const total = visible.reduce((sum, receipt) => sum + receipt.total, 0)

  return (
    <>
      <div className="nota-heading nota-history-heading">
        <div><h1>Riwayat nota</h1><p>{receipts.length} nota tercatat</p></div>
        <button className="nota-primary nota-export" disabled={!visible.length} onClick={() => exportReceipts(visible)}><Icon name="download" /> Ekspor CSV</button>
      </div>
      <section className="nota-order-panel nota-history-filters" aria-label="Filter riwayat">
        <div className="nota-history-search">
          <label className="nota-item-search"><Icon name="search" /><input type="search" aria-label="Cari nomor nota atau nama toko" placeholder="Cari nomor nota atau nama toko" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <label className="nota-history-date">Tanggal <input type="date" value={date} onChange={(event) => { setDate(event.target.value); setPeriod('all') }} /></label>
        </div>
        <div className="nota-categories nota-history-chips" role="group" aria-label="Rentang waktu">
          {historyPeriods.map(([value, label]) => <button key={value} aria-pressed={!date && period === value} onClick={() => { setPeriod(value); setDate('') }}>{label}</button>)}
        </div>
        <div className="nota-categories nota-history-chips" role="group" aria-label="Status nota">
          {Object.entries({ all: 'Semua', ...historyStatuses }).map(([value, label]) => {
            const count = value === 'all' ? matchingTime.length : matchingTime.filter((receipt) => receipt.status === value).length
            return <button key={value} aria-pressed={status === value} onClick={() => setStatus(value)}>{label} ({count})</button>
          })}
        </div>
      </section>
      <p className="nota-history-summary" role="status">{visible.length} nota · total <strong>{money(total)}</strong></p>
      <div className="nota-order-panel nota-history-table">
        <table aria-label="Riwayat nota">
          <thead><tr>{['Nomor', 'Pelanggan', 'Waktu', 'Total', 'Status', 'Sinkron'].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>
            {visible.map((receipt) => {
              const dateLabel = receipt.date === today ? 'Hari ini' : receipt.date === yesterday ? 'Kemarin' : formatReceiptDate(receipt.date)
              const synced = syncStatus(receipt) === 'success'
              return (
                <tr key={receipt.number} className="nota-history-row" onClick={() => openReceipt(receipt.number)}>
                  <th scope="row"><button type="button" className="nota-history-open" aria-label={'Lihat nota ' + receipt.number + ' untuk ' + receipt.customer.name} onClick={(event) => { event.stopPropagation(); openReceipt(receipt.number) }}>{receipt.number}</button></th>
                  <td><strong>{receipt.customer.name}</strong><small>{receipt.customer.area || '—'}</small></td>
                  <td><time dateTime={receipt.date + 'T' + receipt.time.replace('.', ':')}>{dateLabel}, {receipt.time}</time></td>
                  <td><strong>{money(receipt.total)}</strong></td>
                  <td><span className={'nota-history-status nota-history-' + receipt.status}>{historyStatuses[receipt.status]}</span></td>
                  <td><span className={'nota-history-sync' + (synced ? '' : ' nota-history-pending')} role="img" aria-label={syncLabel(receipt)}><Icon name={synced ? 'syncOk' : 'syncPending'} /></span></td>
                </tr>
              )
            })}
            {!visible.length && <tr><td colSpan={6}>Tidak ada nota yang cocok dengan filter.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  )
}

function ItemIcon({ item }) {
  return <span className={'nota-item-icon nota-item-' + item.icon}><Icon name={item.icon} /></span>
}

function ItemCard({ item, quantity, setQuantity }) {
  return (
    <article className={'nota-item-card' + (quantity ? ' nota-item-selected' : '')}>
      <div className="nota-item-head">
        <ItemIcon item={item} />
        <div><h2>{item.name}</h2><strong>{money(item.price)}</strong> <span className="nota-muted">/ {item.unit}</span></div>
      </div>
      <div className="nota-item-controls">
        <span className="nota-muted">Stok {item.stock} {item.unit}</span>
        <div className="nota-quantity">
          <button type="button" aria-label={'Kurangi ' + item.name} disabled={!quantity} onClick={() => setQuantity(Math.max(0, quantity - 1))}>−</button>
          <output aria-label={'Jumlah ' + item.name}>{quantity}</output>
          <button type="button" className="nota-primary" aria-label={'Tambah ' + item.name} disabled={quantity >= item.stock} onClick={() => setQuantity(Math.min(quantity + 1, item.stock))}>+</button>
        </div>
      </div>
    </article>
  )
}

function Total({ total }) {
  return <div className="nota-total"><span>Total</span><strong>{money(total)}</strong></div>
}

function subtotal(item) {
  return Math.round(Math.round(item.price * 100) * Math.round(item.quantity * 1000) / 1000) / 100
}

function ItemRows({ items, remove }) {
  return items.map((item) => (
    <div className="nota-order-row" key={itemKey(item)}>
      <ItemIcon item={item} />
      <div>
        <strong>{item.name}</strong>
        <div className="nota-muted">{item.quantity} {item.unit} × {remove ? thousands.format(item.price) : money(item.price)}</div>
        {remove && <strong>{money(subtotal(item))}</strong>}
      </div>
      {remove
        ? <button type="button" className="nota-text-button" aria-label={'Hapus ' + item.name} onClick={() => remove(itemKey(item))}><Icon name="trash" /></button>
        : <strong>{money(subtotal(item))}</strong>}
    </div>
  ))
}

function Sidebar({ view, setView, pendingCount }) {
  const [expanded, setExpanded] = useState(false)
  const menus = [
    ['new', 'receipt', 'Nota baru'], ['history', 'history', 'Riwayat'],
    ['products', 'box', 'Produk'], ['customers', 'shop', 'Pelanggan'],
    ['backup', 'archive', 'Backup'], ['sync', 'sync', 'Sinkron'],
  ]

  return (
    <aside className={'nota-sidebar' + (expanded ? ' nota-menu-expanded' : '')}>
      <a className="nota-brand" href="/nota-baru">
        <span className="nota-logo" aria-hidden="true"><i /></span>
        <span><strong>Indo Telur</strong><small>Nota digital</small></span>
      </a>
      <button type="button" className="nota-menu-toggle" aria-expanded={expanded} aria-controls="nota-navigation" onClick={() => setExpanded(!expanded)}>
        <span aria-hidden="true">{expanded ? '×' : '☰'}</span> Menu
      </button>
      <nav id="nota-navigation" aria-label="Menu nota">
        {menus.map(([key, icon, label]) => (
          <Fragment key={key}>
            {key === 'backup' && <hr />}
            <button type="button" className={view === key ? 'nota-selected' : ''} aria-current={view === key ? 'page' : undefined}
              onClick={() => { setExpanded(false); setView(key) }}>
              <Icon name={icon} /> {label}{key === 'sync' && pendingCount > 0 && <span className="nota-count">{pendingCount}</span>}
            </button>
          </Fragment>
        ))}
      </nav>
      <div className="nota-exit"><a href="/katalog-api"><Icon name="exit" /> Keluar</a></div>
    </aside>
  )
}

export default function ReceiptPage({ initialView = 'new' }) {
  const [directory, setDirectory] = useState([])
  const [items, setItems] = useState([])
  const [view, setView] = useState(initialView)
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [customer, setCustomer] = useState(null)
  const [step, setStep] = useState(0)
  const [quantities, setQuantities] = useState({})
  const [savedReceipts, setReceipts] = useState([])
  const [queue, setQueue] = useState(readReceiptQueue)
  const queueRef = useRef(queue)
  const [receiptNumber, setReceiptNumber] = useState(null)
  const [lastBackup, setLastBackup] = useState('')
  const [lastSync, setLastSync] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [operationError, setOperationError] = useState('')
  const [busy, setBusy] = useState(false)
  const inProgress = useRef(false)
  const [notice, setNotice] = useState('')
  const [itemQuery, setItemQuery] = useState('')
  const [category, setCategory] = useState('Semua')
  const [saveAs, setSaveAs] = useState('ready')

  function applySnapshot(data) {
    setDirectory(data.customers)
    setItems(data.items)
    setReceipts(data.receipts)
    setLastBackup(data.lastBackup ? formatBackupDate(new Date(data.lastBackup)) : 'Belum ada backup')
    setLastSync(data.lastSync ? formatBackupDate(new Date(data.lastSync)) : '')
    setLoadError('')
    const sentIds = new Set(data.receipts.map((receipt) => receipt.clientId))
    const remaining = queueRef.current.filter(({ payload }) => !sentIds.has(payload.clientId))
    if (remaining.length !== queueRef.current.length) updateQueue(remaining)
  }

  async function refresh(signal) {
    try {
      const data = await dashboardRequest('', 'GET', undefined, signal)
      if (!signal?.aborted) applySnapshot(data)
    } catch (error) {
      if (!signal?.aborted) setLoadError(error.message)
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    refresh(controller.signal)
    return () => controller.abort()
  }, [])

  function updateQueue(entries) {
    saveReceiptQueue(entries)
    queueRef.current = entries
    setQueue(entries)
  }

  async function mutate(action) {
    if (inProgress.current) return false
    inProgress.current = true
    setBusy(true)
    setOperationError('')
    try {
      await action()
      return true
    } catch (error) {
      setOperationError(error.message)
      return false
    } finally {
      inProgress.current = false
      setBusy(false)
    }
  }

  const receipts = [
    ...queue.filter(({ payload }) => !savedReceipts.some((receipt) => receipt.clientId === payload.clientId)).map(({ receipt }) => receipt),
    ...savedReceipts,
  ]
  const matched = directory.filter(({ name, owner }) =>
    (name + ' ' + owner).toLocaleLowerCase('id-ID').includes(query.trim().toLocaleLowerCase('id-ID')),
  )
  const pendingCount = receipts.filter((receipt) => syncStatus(receipt) !== 'success').length
  const availableItems = items.filter((item) => !item.archived)
  const activeReceipt = receipts.find((receipt) => receipt.number === receiptNumber)
  const categories = ['Semua', ...new Set(availableItems.map(({ category }) => category))]
  const visibleItems = availableItems.filter((item) =>
    (category === 'Semua' || category === item.category) &&
    item.name.toLocaleLowerCase('id-ID').includes(itemQuery.trim().toLocaleLowerCase('id-ID')),
  )
  const selectedItems = availableItems
    .map((item) => ({ ...item, quantity: readQuantity(quantities, itemKey(item)) }))
    .filter(({ quantity }) => quantity > 0)
  const total = selectedItems.reduce((sum, item) => sum + subtotal(item), 0)

  function openView(nextView) {
    setReceiptNumber(null)
    setView(nextView)
    setQuery('')
    setAdding(false)
    setNotice('')
    setOperationError('')
    window.scrollTo(0, 0)
    if (nextView !== 'customers') {
      setStep(0)
      setQuantities({})
      setItemQuery('')
      setCategory('Semua')
      setSaveAs('ready')
    }
  }

  function chooseCustomer(entry) {
    setCustomer(entry)
    setView('new')
    setStep(1)
    setNotice('')
  }

  async function addCustomer(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const name = form.get('name').trim()
    const owner = form.get('owner').trim()
    const area = form.get('area').trim()
    if (!name) return
    await mutate(async () => {
      await dashboardRequest('/customers', 'POST', { name, owner, area, phone: form.get('phone').trim() })
      await refresh()
      setQuery('')
      setAdding(false)
      setNotice('Pelanggan ' + name + ' berhasil ditambahkan.')
    })
  }

  async function saveReceipt() {
    await mutate(async () => {
      const clientId = crypto.randomUUID()
      const lines = selectedItems.map(({ key, name, unit, quantity, price }) => ({ key, name, unit, quantity, price }))
      const payload = { clientId, customerId: customer.id, status: saveAs, createdAt: new Date().toISOString(), items: lines.map(({ key, quantity, price }) => ({ key, quantity, price })) }
      const receipt = { number: 'Lokal-' + clientId.slice(0, 8), date: historyDate(), time: formatTime(new Date()), customer, total, status: saveAs, quantities, lines, pending: true, local: true }
      updateQueue([...queue, { payload, receipt }])
      let message
      try {
        const saved = await dashboardRequest('/receipts', 'POST', payload)
        const snapshot = await dashboardRequest()
        applySnapshot(snapshot)
        message = 'Nota ' + saved.number + ' tersimpan.'
      } catch (error) {
        if (!error.offline) {
          updateQueue(queueRef.current.filter(({ payload }) => payload.clientId !== clientId))
          await refresh()
          throw error
        }
        message = 'Nota disimpan di antrean perangkat. Kirim lewat menu Sinkron saat koneksi kembali.'
      }
      openView('new')
      setNotice(message)
    })
  }

  async function updateReceiptStatus(receipt, status) {
    return mutate(async () => {
      await dashboardRequest('/receipts/' + encodeURIComponent(receipt.number) + '/status', 'PATCH', { status })
      await refresh()
    })
  }

  async function restoreBackup(data) {
    return mutate(async () => {
      if (queue.length) throw new Error('Selesaikan antrean sinkron sebelum memulihkan backup.')
      applySnapshot(await dashboardRequest('/restore', 'POST', data))
    })
  }

  async function syncReceipts() {
    await mutate(async () => {
      const remaining = []
      for (const entry of queue) {
        try {
          await dashboardRequest('/receipts', 'POST', entry.payload)
        } catch (error) {
          remaining.push({ ...entry, receipt: { ...entry.receipt, failed: !error.offline, syncError: error.message } })
        }
      }
      updateQueue(remaining)
      await refresh()
    })
  }

  function discardReceipt(number) {
    if (!window.confirm('Hapus nota ini dari antrean perangkat?')) return
    return mutate(() => updateQueue(queue.filter(({ receipt }) => receipt.number !== number)))
  }

  function changeQuantity(name, quantity) {
    setQuantities((current) => ({ ...current, [name]: quantity }))
  }

  function saveItem(values, existing) {
    return mutate(async () => {
      await dashboardRequest('/products' + (existing ? '/' + existing.key : ''), existing ? 'PUT' : 'POST', { ...values, expectedStock: existing?.stock })
      await refresh()
    })
  }

  function archiveItem(entry) {
    return mutate(async () => {
      await dashboardRequest('/products/' + entry.key, 'DELETE')
      await refresh()
    })
  }

  return (
    <div className="nota-page">
      <Sidebar view={view} setView={openView} pendingCount={pendingCount} />
      <div className="nota-workspace">
        <header className="nota-topbar">
          <div><strong>Toko Indo Telur · Bontang</strong><div className="nota-date">{longHistoryDate.format(new Date())}</div></div>
          <div className="nota-account">
            <span className="nota-online"><Icon name="wifi" /> {loading ? 'Memuat' : loadError ? 'Terputus' : 'Online'}</span>
            <span className="nota-avatar">N</span><strong>Ibu Nasikah</strong>
          </div>
        </header>

        <main className="nota-content">
          {loading && <p className="nota-message" role="status">Memuat data toko…</p>}
          {loadError && <p className="nota-message nota-backup-error" role="alert">{loadError} <button className="nota-text-button" onClick={() => refresh()}>Coba lagi</button></p>}
          {operationError && !adding && <p className="nota-message nota-backup-error" role="alert">{operationError}</p>}
          {view === 'new' && <div className="nota-heading">
            <div>
              <h1>Buat nota</h1>
              {view === 'new' && <p>Tiga langkah: pilih pelanggan, isi barang, lalu simpan.</p>}
            </div>
            {view === 'new' && (
              <ol className="nota-steps" aria-label="Langkah pembuatan nota">
                {['Pelanggan', 'Barang', 'Simpan'].map((label, index) => (
                  <li key={label} className={index < step ? 'nota-step-done' : undefined} aria-current={step === index ? 'step' : undefined}><span>{index < step ? <Icon name="check" /> : index + 1}</span>{label}</li>
                ))}
              </ol>
            )}
          </div>}

          {notice && <p className="nota-message" role="status">{notice}</p>}

          {view === 'new' && step === 0 && (
            <>
              <div className="nota-tools">
                <input type="search" aria-label="Cari nama toko atau pemilik" placeholder="Cari nama toko atau pemilik" value={query} onChange={(event) => setQuery(event.target.value)} />
                <button type="button" onClick={() => { setAdding(true); setNotice('') }} aria-haspopup="dialog"><Icon name="person" /> Pelanggan baru</button>
              </div>

              {adding && <CustomerForm save={addCustomer} close={() => setAdding(false)} busy={busy} error={operationError} />}

              <div className="nota-grid">
                {matched.map((entry) => (
                  <button type="button" className="nota-card" key={directory.indexOf(entry)} onClick={() => chooseCustomer(entry)}>
                    <span className="nota-initial" aria-hidden="true">{entry.initial}</span>
                    <span className="nota-card-copy">
                      <strong>{entry.name}</strong>
                    <span>{[entry.owner, entry.area].filter(Boolean).join(' · ')}</span>
                    <small>{customerLastOrder(receipts, entry)}</small>
                    </span>
                    <Icon name="arrow" />
                  </button>
                ))}
              </div>
              {matched.length === 0 && <p className="nota-message">Pelanggan tidak ditemukan.</p>}
              {view === 'new' && <p className="nota-repeat">Mau mengulang pesanan lama? <button onClick={() => openView('customers')}>Buka daftar pelanggan</button></p>}
            </>
          )}

          {view === 'new' && step === 1 && (
            <div className="nota-order-layout">
              <div className="nota-product-picker">
                <div className="nota-order-panel nota-customer-bar">
                  <Icon name="shop" />
                  <div><strong>{customer.name}</strong><div className="nota-muted">{customer.address || customer.area}</div></div>
                  <button className="nota-text-button" onClick={() => { setStep(0); setQuery(''); window.scrollTo(0, 0) }}>Ganti</button>
                </div>
                <label className="nota-item-search"><Icon name="search" /><input type="search" aria-label="Cari barang" placeholder="Cari barang, misal: telur" value={itemQuery} onChange={(event) => setItemQuery(event.target.value)} /></label>
                <div className="nota-categories" role="group" aria-label="Kategori barang">
                  {categories.map((label) => <button key={label} aria-pressed={category === label} onClick={() => setCategory(label)}>{label}</button>)}
                </div>
                <div className="nota-item-grid">
                  {visibleItems.map((item) => <ItemCard key={itemKey(item)} item={item} quantity={readQuantity(quantities, itemKey(item))} setQuantity={(quantity) => changeQuantity(itemKey(item), quantity)} />)}
                </div>
                {!visibleItems.length && <p className="nota-muted">Barang tidak ditemukan.</p>}
              </div>
              {selectedItems.length > 0 && <a className="nota-cart-shortcut" href="#nota-cart">Keranjang · {money(total)} <Icon name="arrow" /></a>}
              <section id="nota-cart" className="nota-order-panel nota-cart" aria-labelledby="nota-cart-title" tabIndex={-1}>
                <div className="nota-order-header">
                  <h2 id="nota-cart-title">Keranjang nota</h2><span className="nota-cart-count">{selectedItems.length} barang</span>
                </div>
                {selectedItems.length
                  ? <div className="nota-order-rows"><ItemRows items={selectedItems} remove={(key) => changeQuantity(key, 0)} /></div>
                  : <div className="nota-cart-empty"><Icon name="basket" /><strong>Keranjang masih kosong</strong><p>Tekan tombol + pada barang.</p></div>}
                <div className="nota-cart-footer">
                  <Total total={total} />
                  <button className="nota-primary nota-wide-button" disabled={!selectedItems.length} onClick={() => { setStep(2); window.scrollTo(0, 0) }}>Lanjut simpan nota <Icon name="arrow" /></button>
                </div>
              </section>
            </div>
          )}

          {view === 'new' && step === 2 && (
            <div className="nota-order-layout">
              <div className="nota-review">
                <section className="nota-order-panel nota-recipient">
                  <p className="nota-muted">Nota untuk</p>
                  <h2>{customer.name}</h2>
                  <p className="nota-muted">{customer.address || customer.area}</p>
                </section>
                <section className="nota-order-panel">
                  <div className="nota-order-header"><h2>Periksa barang</h2><button className="nota-text-button" onClick={() => setStep(1)}><Icon name="back" /> Ubah barang</button></div>
                  <div className="nota-order-rows"><ItemRows items={selectedItems} /></div>
                </section>
              </div>
              <form className="nota-order-panel nota-save" onSubmit={(event) => { event.preventDefault(); saveReceipt() }}>
                <fieldset>
                  <legend>Simpan sebagai</legend>
                  <label><input type="radio" name="nota-status" value="ready" checked={saveAs === 'ready'} onChange={() => setSaveAs('ready')} /><span><strong>Siap diantar</strong><small>Stok langsung berkurang.</small></span></label>
                  <label><input type="radio" name="nota-status" value="draft" checked={saveAs === 'draft'} onChange={() => setSaveAs('draft')} /><span><strong>Draft</strong><small>Belum final. Stok belum berkurang.</small></span></label>
                </fieldset>
                <Total total={total} />
                <button className="nota-primary nota-wide-button" disabled={busy || !selectedItems.length}>{busy ? 'Menyimpan…' : 'Simpan nota'}</button>
              </form>
            </div>
          )}

          {view === 'history' && <>
            <div hidden={Boolean(activeReceipt)}><ReceiptHistory receipts={receipts} openReceipt={(number) => { setReceiptNumber(number); window.scrollTo(0, 0) }} /></div>
            {activeReceipt && <ReceiptDetail key={activeReceipt.number} receipt={activeReceipt} items={items}
              back={() => { setReceiptNumber(null); setOperationError(''); window.scrollTo(0, 0) }} updateStatus={updateReceiptStatus} busy={busy} />}
          </>}
          {view === 'customers' && <CustomersView customers={directory} receipts={receipts} items={items}
            add={() => { openView('new'); setAdding(true) }}
            repeat={(entry, receipt) => {
              openView('new')
              chooseCustomer(entry)
              setQuantities(Object.fromEntries(availableItems.map((item) => [itemKey(item), Math.min(item.stock, readQuantity(receipt.quantities, itemKey(item)))])))
              setNotice('Periksa barang dan jumlah sebelum menyimpan nota baru.')
            }} />}
          {view === 'products' && <ProductsView items={availableItems} save={saveItem} archive={archiveItem} busy={busy} />}
          {view === 'backup' && <BackupView items={items} customers={directory} receipts={savedReceipts} lastBackup={lastBackup} setLastBackup={setLastBackup} restore={restoreBackup} busy={busy} />}
          {view === 'sync' && <SyncView receipts={receipts} lastSync={lastSync} sync={syncReceipts} discard={discardReceipt} busy={busy} />}
        </main>
      </div>
    </div>
  )
}

function formatTime(date) {
  return new Intl.DateTimeFormat('id-ID', { timeZone: 'Asia/Makassar', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date).replace(':', '.')
}

function formatReceiptDate(date) {
  return shortHistoryDate.format(new Date(date + 'T00:00:00+08:00'))
}

function formatBackupDate(date) {
  return shortHistoryDate.format(date) + ', ' + formatTime(date)
}

function readQuantity(quantities, name) {
  return quantities && Object.hasOwn(quantities, name) ? quantities[name] : 0
}

function itemKey(item) {
  return item.key ?? item.name
}

function BackupView({ items, customers, receipts, lastBackup, setLastBackup, restore, busy }) {
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function exportBackup() {
    setError('')
    setMessage('')
    try {
      const data = await dashboardRequest('/backup', 'POST')
      downloadFile('backup-indo-telur-' + historyDate() + '.json', new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      setLastBackup(formatBackupDate(new Date(data.createdAt)))
      setMessage('File backup siap diunduh.')
    } catch (error) {
      setError(error.message)
    }
  }

  async function importBackup(event) {
    const file = event.target.files[0]
    event.target.value = ''
    if (!file) return
    setMessage('')
    setError('')
    let data
    try {
      data = JSON.parse(await file.text())
      if (data?.version !== 2) throw new Error()
    } catch {
      setError('File backup tidak valid. Pilih file JSON hasil ekspor dari aplikasi ini.')
      return
    }
    if (!window.confirm('Pulihkan data dari file ini ke database kosong?')) return
    if (await restore(data)) setMessage('Data berhasil dipulihkan.')
  }

  return (
    <div className="nota-maintenance">
      <div className="nota-heading"><div><h1>Backup dan pulihkan</h1><p>Simpan salinan data ke file, lalu pulihkan jika ganti HP atau data hilang.</p></div></div>
      {message && <p className="nota-message" role="status">{message}</p>}
      {error && <p className="nota-message nota-backup-error" role="alert">{error}</p>}
      <div className="nota-backup-grid">
        <section className="nota-order-panel nota-backup-card">
          <span className="nota-maintenance-icon"><Icon name="archive" /></span>
          <h2>Simpan cadangan</h2>
          <p>Produk, pelanggan, dan nota yang tersimpan di PostgreSQL dicadangkan ke satu file.</p>
          <div className="nota-last-backup"><Icon name="shield" /> <span>Backup terakhir: <strong>{lastBackup}</strong></span></div>
          <dl className="nota-backup-counts">
            {[['Produk', items.filter((item) => !item.archived).length], ['Pelanggan', customers.length], ['Nota', receipts.length]].map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{count}</dd></div>)}
          </dl>
          <button className="nota-primary nota-wide-button" disabled={busy} onClick={exportBackup}><Icon name="download" /> Ekspor file backup</button>
        </section>
        <section className="nota-order-panel nota-backup-card">
          <span className="nota-maintenance-icon nota-restore-icon"><Icon name="upload" /></span>
          <h2>Pulihkan dari file</h2>
          <p>Pilih file backup (.json) dari aplikasi ini untuk memulihkan data ke database kosong.</p>
          <label className="nota-file-button"><input type="file" accept=".json,application/json" disabled={busy} onChange={importBackup} /><Icon name="file" /> Pilih file backup</label>
        </section>
      </div>
    </div>
  )
}

const syncStatuses = {
  pending: ['Menunggu', 'clock'],
  failed: ['Gagal', 'syncPending'],
  success: ['Berhasil', 'syncOk'],
}

function syncStatus(receipt) {
  return receipt.failed ? 'failed' : receipt.pending ? 'pending' : 'success'
}

function syncLabel(receipt) {
  const status = syncStatus(receipt)
  return status === 'success' ? 'Tersinkron' : syncStatuses[status][0]
}

function SyncView({ receipts, lastSync, sync, discard, busy }) {
  const [filter, setFilter] = useState('all')
  const counts = { pending: 0, failed: 0, success: 0 }
  for (const receipt of receipts) counts[syncStatus(receipt)]++
  const hasQueue = counts.pending + counts.failed > 0
  const visible = receipts.filter((receipt) => filter === 'all' || syncStatus(receipt) === filter)
  const today = historyDate()
  const yesterday = historyDate(1)

  return (
    <div className="nota-maintenance">
      <div className="nota-heading nota-history-heading">
        <div><h1>Status sinkron</h1><p>{lastSync ? 'Terakhir tersinkron ' + lastSync : 'Belum ada sinkronisasi di sesi ini.'}</p></div>
        <button className="nota-primary nota-export nota-sync-button" disabled={!hasQueue || busy} onClick={() => { sync(); setFilter('all') }}><Icon name="sync" /> {busy ? 'Menyinkronkan…' : 'Sinkronkan sekarang'}</button>
      </div>
      <p className={'nota-sync-banner ' + (hasQueue ? 'nota-sync-pending' : 'nota-sync-success')} role="status"><Icon name={hasQueue ? 'clock' : 'syncOk'} />{hasQueue ? 'Ada nota dalam antrean sinkronisasi' : 'Semua nota sudah tersinkron'}</p>
      <dl className="nota-sync-counts">
        {Object.entries(syncStatuses).map(([key, [label, icon]]) => (
          <div className="nota-order-panel" key={key}>
            <span className={'nota-maintenance-icon nota-sync-' + key}><Icon name={icon} /></span>
            <div><dt>{label}</dt><dd>{counts[key]}</dd></div>
          </div>
        ))}
      </dl>
      <div className="nota-categories nota-sync-filters" role="group" aria-label="Filter sinkronisasi">
        {Object.entries({ all: ['Semua'], ...syncStatuses }).map(([key, [label]]) => <button key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}
      </div>
      <ul className="nota-order-panel nota-sync-list">
        {visible.map((receipt) => {
          const status = syncStatus(receipt)
          const [label, icon] = syncStatuses[status]
          const day = receipt.date === today ? 'Hari ini' : receipt.date === yesterday ? 'Kemarin' : formatReceiptDate(receipt.date)
          return (
            <li key={receipt.number}>
              <div><strong><code>{receipt.number}</code> · {receipt.customer.name}</strong><p>{day}, {receipt.time} · {money(receipt.total)}</p>{receipt.syncError && <p>{receipt.syncError}</p>}</div>
              <div><span className={'nota-sync-badge nota-sync-' + status}><Icon name={icon} />{status === 'success' ? 'Tersinkron' : label}</span>
                {receipt.local && receipt.failed && <button className="nota-text-button" disabled={busy} onClick={() => discard(receipt.number)}>Hapus dari antrean</button>}
              </div>
            </li>
          )
        })}
        {!visible.length && <li>Tidak ada nota untuk status ini.</li>}
      </ul>
    </div>
  )
}

const productCategories = ['Telur', 'Beras', 'Minyak', 'Gula', 'Tepung', 'Mi instan', 'Kopi', 'Lainnya']
const productIcons = { Telur: 'egg', Beras: 'grain', Minyak: 'oil', Tepung: 'grain' }

function ProductsView({ items, save, archive, busy }) {
  const [query, setQuery] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [editor, setEditor] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const lowStockCount = items.filter((item) => item.stock <= 5).length
  const search = query.trim().toLocaleLowerCase('id-ID')
  const visible = items.filter((item) => item.name.toLocaleLowerCase('id-ID').includes(search) && (!lowOnly || item.stock <= 5))
  const categories = [...new Set([...productCategories, ...items.map((item) => item.category)])]

  function openEditor(item) {
    setEditor(item)
    setError('')
    setMessage('')
  }

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const name = form.get('name').trim()
    const unit = form.get('unit').trim()
    const category = form.get('category')
    if (!name || !unit) {
      setError('Isi nama dan satuan produk.')
      return
    }
    if (items.some((item) => itemKey(item) !== itemKey(editor) && item.name.toLocaleLowerCase('id-ID') === name.toLocaleLowerCase('id-ID'))) {
      setError('Nama produk sudah digunakan.')
      return
    }
    const icon = Object.hasOwn(productIcons, category) ? productIcons[category] : 'box'
    if (!await save({ name, unit, category, price: Number(form.get('price')), stock: Number(form.get('stock')), icon }, editor.name ? editor : null)) return
    setEditor(null)
    setQuery('')
    setLowOnly(false)
    setMessage('Produk berhasil disimpan.')
  }

  return (
    <div className="nota-products">
      <div className="nota-heading nota-history-heading">
        <div><h1>Produk dan stok</h1><p>{items.length} produk · {lowStockCount} stok menipis atau habis</p></div>
        <button className="nota-primary nota-export" onClick={() => openEditor({})}><Icon name="plus" /> Tambah produk</button>
      </div>
      <p className="nota-products-info"><Icon name="info" /> Mengubah harga hanya berlaku untuk nota baru. Nota lama tetap memakai harga saat nota dibuat.</p>
      {message && <p className="nota-message" role="status">{message}</p>}
      {editor && (
        <form key={editor.name || 'new'} className="nota-order-panel nota-product-form" onSubmit={submit}>
          <h2>{editor.name ? 'Ubah produk' : 'Tambah produk'}</h2>
          <div>
            <label>Nama produk<input name="name" defaultValue={editor.name} required /></label>
            <label>Kategori<select name="category" defaultValue={editor.category ?? 'Lainnya'}>{categories.map((category) => <option key={category}>{category}</option>)}</select></label>
            <label>Satuan<input name="unit" defaultValue={editor.unit} required /></label>
            <label>Harga (Rp)<input name="price" type="number" min="0" max="999999999999.99" step="0.01" defaultValue={editor.price} required /></label>
            <label>Stok<input name="stock" type="number" min="0" max="99999999999.999" step="0.001" defaultValue={editor.stock ?? 0} required /></label>
          </div>
          {error && <p className="nota-backup-error" role="alert">{error}</p>}
          <footer>
            <button type="button" onClick={() => setEditor(null)}>Batal</button>
            <button className="nota-primary" type="submit" disabled={busy}>Simpan produk</button>
          </footer>
        </form>
      )}
      <div className="nota-products-tools">
        <label className="nota-item-search"><Icon name="search" /><input type="search" aria-label="Cari produk" placeholder="Cari produk" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <div className="nota-categories" role="group" aria-label="Filter stok">
          <button aria-pressed={!lowOnly} onClick={() => setLowOnly(false)}>Semua</button>
          <button aria-pressed={lowOnly} onClick={() => setLowOnly(true)}>Stok menipis ({lowStockCount})</button>
        </div>
      </div>
      <div className="nota-order-panel nota-history-table nota-products-table">
        <table aria-label="Produk dan stok">
          <thead><tr>
            <th scope="col">Produk</th><th scope="col">Satuan</th>
            <th scope="col">Harga</th>
            <th scope="col">Stok</th>
            <th scope="col" aria-label="Aksi" />
          </tr></thead>
          <tbody>
            {visible.map((item) => (
              <tr key={itemKey(item)}>
                <th scope="row"><span className="nota-product-name"><ItemIcon item={item} />{item.name}</span></th>
                <td>{item.unit}</td>
                <td><strong>{money(item.price)}</strong></td>
                <td><span className={'nota-product-stock' + (item.stock <= 5 ? ' nota-sync-pending' : '')}>{item.stock} {item.unit}</span></td>
                <td><div className="nota-product-actions">
                  <button className="nota-text-button" aria-label={'Ubah ' + item.name} onClick={() => openEditor(item)}><Icon name="edit" /> Ubah</button>
                  <button className="nota-text-button nota-delete" disabled={busy} aria-label={'Hapus ' + item.name} onClick={async () => {
                    if (!window.confirm('Hapus "' + item.name + '" dari daftar produk?')) return
                    if (!await archive(item)) return
                    if (editor?.name && itemKey(editor) === itemKey(item)) setEditor(null)
                    setMessage('Produk dihapus dari daftar.')
                  }}><Icon name="trash" /> Hapus</button>
                </div></td>
              </tr>
            ))}
            {!visible.length && <tr><td colSpan={5}>Tidak ada produk yang cocok.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CustomerForm({ save, close, busy, error }) {
  return (
    <dialog className="nota-customer-dialog" aria-labelledby="nota-customer-title"
      ref={(element) => { if (element && !element.open) element.showModal() }}
      onCancel={(event) => { event.preventDefault(); close() }}>
      <form onSubmit={save}>
        <header><h2 id="nota-customer-title">Pelanggan baru</h2><button type="button" aria-label="Tutup" onClick={close}>×</button></header>
        <div className="nota-customer-fields">
          <label>Nama toko<input name="name" placeholder="Misal: Toko Berkah Jaya" required pattern=".*\S.*" /></label>
          <label>Nama pemilik (boleh kosong)<input name="owner" /></label>
          <label>Nomor HP (boleh kosong)<input name="phone" type="tel" placeholder="0812..." /></label>
          <label>Alamat (boleh kosong)<input name="area" placeholder="Jalan, kelurahan" /></label>
          {error && <p className="nota-backup-error" role="alert">{error}</p>}
        </div>
        <footer><button type="button" onClick={close}>Batal</button><button type="submit" disabled={busy} className="nota-primary">Simpan pelanggan</button></footer>
      </form>
    </dialog>
  )
}

function customerKey(customer) {
  return customer.id ?? JSON.stringify([customer.name, customer.owner, customer.area])
}

function customerLastOrder(receipts, customer) {
  const receipt = receipts.find((entry) => customerKey(entry.customer) === customerKey(customer))
  return receipt ? 'Terakhir: ' + receipt.lines.length + ' barang · ' + money(receipt.total) : 'Belum ada nota'
}

function CustomersView({ customers, receipts, items, add, repeat }) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)
  const search = query.trim().toLocaleLowerCase('id-ID')
  const visible = customers.filter((entry) => (entry.name + ' ' + entry.owner).toLocaleLowerCase('id-ID').includes(search))
  const active = visible.find((entry) => customerKey(entry) === selected) ?? visible[0]
  const ordersFor = (entry) => receipts.filter((receipt) => customerKey(receipt.customer) === customerKey(entry))
  const orders = active ? ordersFor(active) : []
  const latest = orders.find((receipt) => items.some((item) => !item.archived && readQuantity(receipt.quantities, itemKey(item)) > 0))

  return (
    <>
      <div className="nota-heading nota-history-heading">
        <div><h1>Pelanggan</h1><p>{customers.length} toko pelanggan</p></div>
        <button className="nota-export" onClick={add}><Icon name="person" /> Tambah pelanggan</button>
      </div>
      <div className="nota-customer-layout">
        <div className="nota-customer-list">
          <input type="search" aria-label="Cari toko atau pemilik" placeholder="Cari toko atau pemilik" value={query} onChange={(event) => setQuery(event.target.value)} />
          {visible.map((entry) => (
            <button key={customerKey(entry)} aria-pressed={entry === active} onClick={() => setSelected(customerKey(entry))}>
              <span className="nota-initial">{entry.initial}</span>
              <span><strong>{entry.name}</strong><span className="nota-muted">{[entry.owner, ordersFor(entry).length + ' nota'].filter(Boolean).join(' · ')}</span></span>
            </button>
          ))}
          {!visible.length && <p className="nota-muted">Pelanggan tidak ditemukan.</p>}
        </div>
        {active && <div className="nota-customer-detail">
          <section className="nota-order-panel nota-customer-profile">
            <h2>{active.name}</h2>
            {active.owner && <p>{active.owner}</p>}
            <div className="nota-customer-contact nota-muted">{active.phone && <span>☎ {active.phone}</span>}{(active.address || active.area) && <span><Icon name="shop" />{active.address || active.area}</span>}</div>
            <dl><div><dt>Jumlah nota</dt><dd>{orders.length}</dd></div><div><dt>Total belanja</dt><dd>{money(orders.reduce((total, receipt) => total + receipt.total, 0))}</dd></div></dl>
            <button className="nota-primary nota-export" disabled={!latest} onClick={() => repeat(active, latest)}><Icon name="history" /> Ulang pesanan terakhir</button>
          </section>
          <h2>Riwayat pesanan</h2>
          {orders.map((receipt) => {
            const canRepeat = items.some((item) => !item.archived && readQuantity(receipt.quantities, itemKey(item)) > 0)
            const lines = receipt.lines
            const date = receipt.date === historyDate() ? 'Hari ini' : receipt.date === historyDate(1) ? 'Kemarin' : formatReceiptDate(receipt.date)
            return <article key={receipt.number} className="nota-order-panel nota-customer-order">
              <header><span><code>{receipt.number}</code> <span className={'nota-history-status nota-history-' + receipt.status}>{historyStatuses[receipt.status]}</span></span><strong>{money(receipt.total)}</strong></header>
              <div><div><p className="nota-muted">{date}, {receipt.time}</p>{lines.length > 0 && <p>{lines.map((line) => line.name + ' ' + line.quantity + ' ' + line.unit).join(', ')}</p>}</div>
                <button className="nota-export" disabled={!canRepeat} onClick={() => repeat(active, receipt)}><Icon name="history" /> Ulang pesanan</button>
              </div>
            </article>
          })}
          {!orders.length && <p className="nota-muted">Belum ada pesanan.</p>}
        </div>}
      </div>
    </>
  )
}

function receiptText(receipt, lines) {
  const width = 32
  const rule = '='.repeat(width)
  const divider = '-'.repeat(width)
  const center = (text) => ' '.repeat(Math.max(0, Math.floor((width - text.length) / 2))) + text
  const pair = (left, right) => left + ' '.repeat(Math.max(1, width - left.length - right.length)) + right
  const date = receipt.date.split('-').reverse().join('/')
  return [
    center('TOKO INDO TELUR'), center('Grosir sembako - Bontang'),
    rule, 'No    : ' + receipt.number, 'Tgl   : ' + date + ' ' + receipt.time,
    'Untuk : ' + receipt.customer.name, divider,
    ...lines.flatMap(({ name, unit, quantity, price, subtotal: savedSubtotal }) => [
      name,
      price === undefined ? '  ' + quantity + ' ' + unit
        : pair('  ' + quantity + ' ' + unit + ' x ' + thousands.format(price), thousands.format(savedSubtotal ?? subtotal({ price, quantity }))),
    ]),
    ...(lines.length ? [divider, lines.length + ' jenis barang'] : ['Rincian barang tidak tersedia', divider]),
    pair('TOTAL', money(receipt.total)), rule, center('Terima kasih'), center('Barang sudah diperiksa'),
  ].join('\n')
}

function ReceiptDetail({ receipt, items, back, updateStatus, busy }) {
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const lines = receipt.lines ?? items.flatMap((item) => {
    const quantity = readQuantity(receipt.quantities, itemKey(item))
    return quantity ? [{ name: item.name, unit: item.unit, quantity }] : []
  })
  const text = receiptText(receipt, lines)
  const status = syncStatus(receipt)
  const draft = receipt.status === 'draft'
  const date = formatReceiptDate(receipt.date)
  const address = receipt.customer.address || receipt.customer.area

  async function shareReceipt() {
    setMessage('')
    setError('')
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Nota ' + receipt.number, text })
        return
      } catch (error) {
        if (error.name === 'AbortError') return
      }
    }
    try {
      await navigator.clipboard.writeText(text)
      setMessage('Teks nota disalin.')
    } catch {
      downloadFile(receipt.number + '.txt', new Blob([text], { type: 'text/plain;charset=utf-8' }))
      setMessage('Teks nota siap diunduh.')
    }
  }

  async function mark(nextStatus) {
    setError('')
    setMessage(await updateStatus(receipt, nextStatus) ? 'Status nota diperbarui.' : '')
  }

  return (
    <div className="nota-detail-layout">
      <div className="nota-detail-content">
        {draft && <div className="nota-products-info nota-detail-banner"><Icon name="sync" /><div><strong>Draft {receipt.number} tersimpan</strong><p>Ubah ke "Siap" saat pesanan sudah pasti. Stok baru berkurang saat itu.</p></div></div>}
        <section className="nota-order-panel nota-detail-summary">
          <div className="nota-detail-top">
            <div><p className="nota-muted">{date}, {receipt.time}</p><h1>{receipt.customer.name}</h1>{address && <p className="nota-muted">{address}</p>}</div>
            <div className="nota-detail-badges">
              <span className={'nota-history-status nota-history-' + receipt.status}>{historyStatuses[receipt.status]}</span>
              <span className={'nota-sync-badge nota-sync-' + status}><Icon name={syncStatuses[status][1]} />{syncLabel(receipt)}</span>
            </div>
          </div>
          <dl className="nota-detail-counts">
            <div><dt>Jenis barang</dt><dd>{lines.length || '—'}</dd></div>
            <div><dt>Jumlah satuan</dt><dd>{lines.length ? lines.reduce((sum, line) => sum + line.quantity, 0) : '—'}</dd></div>
          </dl>
          <div className="nota-detail-total"><span>Total</span><strong>{money(receipt.total)}</strong></div>
        </section>
        <div className="nota-detail-actions">
          <button className="nota-primary nota-wide-button" onClick={() => window.print()}><Icon name="print" /> Cetak</button>
          <button className="nota-wide-button" onClick={shareReceipt}><Icon name="share" /> Bagikan</button>
        </div>
        {message && <p className="nota-message" role="status">{message}</p>}
        {error && <p className="nota-backup-error" role="alert">{error}</p>}
        {!receipt.local && receipt.status !== 'delivered' && <section className="nota-order-panel nota-detail-status">
          <h2>Ubah status</h2>
          <div>
            {draft && <button className="nota-export" disabled={busy} onClick={() => mark('ready')}>Tandai siap</button>}
            <button className="nota-export" disabled={busy} onClick={() => mark('delivered')}><Icon name="truck" /> Tandai sudah diantar</button>
          </div>
        </section>}
        <button className="nota-text-button" onClick={back}><Icon name="back" /> Kembali ke riwayat</button>
      </div>
      <figure className="nota-slip">
        <pre>{text}</pre>
        <figcaption>Pratinjau kertas 58 mm · 32 huruf per baris</figcaption>
      </figure>
    </div>
  )
}
