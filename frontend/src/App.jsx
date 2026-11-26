import { useEffect, useState } from 'react'
import './App.css'

const emptyProduct = { name: '', sku: '', price: '', unit: 'pcs', description: '', is_active: true }
const rupiah = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 2, minimumFractionDigits: 0 })

function focusProductName(input) {
  input?.focus()
}

async function productRequest(path = '', options) {
  let response
  try {
    response = await fetch('/api/products' + path, options)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('API produk tidak dapat dijangkau. Pastikan backend berjalan.')
  }

  const result = await response.json().catch(() => null)
  if (!response.ok || !result?.success) {
    throw new Error(result?.message ?? 'API produk tidak dapat dijangkau. Pastikan backend berjalan.')
  }
  return result.data
}

function App() {
  const [products, setProducts] = useState([])
  const [query, setQuery] = useState('')
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [editor, setEditor] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    productRequest('', { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setProducts(data) })
      .catch((error) => { if (!controller.signal.aborted) setLoadError(error.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })

    return () => controller.abort()
  }, [loadAttempt])

  const search = query.trim().toLocaleLowerCase('id-ID')
  const visibleProducts = products.filter(({ name, sku }) =>
    name.toLocaleLowerCase('id-ID').includes(search) ||
    sku?.toLocaleLowerCase('id-ID').includes(search),
  )
  const activeCount = products.filter(({ is_active }) => is_active).length
  const emptyStockCount = products.filter(({ stock, is_active }) => is_active && Number(stock) === 0).length

  function openEditor(product) {
    const values = product
      ? { name: product.name, sku: product.sku ?? '', price: product.price, unit: product.unit, description: product.description ?? '', is_active: product.is_active }
      : { ...emptyProduct }

    setEditor({ id: product?.id, values })
    setFormError('')
    setNotice('')
  }

  async function saveProduct(event) {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setFormError('')

    const { id, values } = editor
    try {
      const saved = await productRequest(id ? '/' + id : '', {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      })
      setProducts((current) => [...current.filter((product) => product.id !== saved.id), saved]
        .sort((a, b) => a.name.localeCompare(b.name, 'id-ID')))
      setNotice(id ? 'Perubahan produk tersimpan.' : 'Produk berhasil ditambahkan.')
      setQuery('')
      setEditor(null)
    } catch (error) {
      setFormError(error.message)
    } finally {
      setSaving(false)
    }
  }

  function updateField(event) {
    const { name, type, value, checked } = event.target
    setEditor((current) => ({
      ...current,
      values: { ...current.values, [name]: type === 'checkbox' ? checked : value },
    }))
  }

  return (
    <>
      <header className="site-header">
        <div className="shell header-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true"><i /></span>
            <span>Toko Indo Telur<small>Grosir sembako</small></span>
          </div>
          <a className="nav-link" href="#produk">Produk</a>
        </div>
      </header>

      <main className="shell">
        <section className="intro" aria-labelledby="page-title">
          <h1 id="page-title">Katalog Produk</h1>
          <p>Kelola daftar produk, harga jual, dan pantau stok toko.</p>
        </section>

        <dl className="stats">
          <div><dt>Total produk</dt><dd>{loading || loadError ? '—' : products.length}</dd></div>
          <div><dt>Produk aktif</dt><dd>{loading || loadError ? '—' : activeCount}</dd></div>
          <div><dt>Stok habis</dt><dd>{loading || loadError ? '—' : emptyStockCount}</dd></div>
        </dl>

        {editor && (
          <section className="panel editor" aria-labelledby="editor-title">
            <h2 id="editor-title">{editor.id ? 'Ubah produk' : 'Tambah produk'}</h2>
            <form onSubmit={saveProduct}>
              <fieldset disabled={saving} className="fields">
                <label>Nama produk<input ref={focusProductName} name="name" value={editor.values.name} onChange={updateField} required /></label>
                <label>SKU<input name="sku" value={editor.values.sku} onChange={updateField} maxLength={64} /></label>
                <label>Harga (Rp)<input name="price" value={editor.values.price} onChange={updateField} type="number" min="0" max="999999999999.99" step="0.01" required /></label>
                <label>Satuan<input name="unit" value={editor.values.unit} onChange={updateField} maxLength={32} required /></label>
                <label className="wide">Deskripsi<textarea name="description" value={editor.values.description} onChange={updateField} rows={2} /></label>
                <label className="checkbox wide"><input name="is_active" type="checkbox" checked={editor.values.is_active} onChange={updateField} /> Produk aktif</label>
              </fieldset>
              {formError && <p className="error" role="alert">{formError}</p>}
              <div className="actions">
                <button className="secondary" type="button" disabled={saving} onClick={() => setEditor(null)}>Batal</button>
                <button disabled={saving}>{saving ? 'Menyimpan…' : 'Simpan produk'}</button>
              </div>
            </form>
          </section>
        )}

        <section className="panel" id="produk" aria-labelledby="products-title">
          <div className="toolbar">
            <h2 id="products-title">Daftar Produk</h2>
            <div className="actions">
              <input type="search" aria-label="Cari produk atau SKU" placeholder="Cari produk atau SKU" value={query} onChange={(event) => setQuery(event.target.value)} />
              <button disabled={loading || Boolean(loadError) || Boolean(editor)} onClick={() => openEditor()}>+ Tambah Produk</button>
            </div>
          </div>
          {notice && <p className="notice" role="status">{notice}</p>}
          {loading && <p className="empty" role="status">Memuat produk…</p>}
          {loadError && (
            <div className="empty">
              <p className="error" role="alert">{loadError}</p>
              <button className="secondary" onClick={() => {
                setLoading(true)
                setLoadError('')
                setLoadAttempt((attempt) => attempt + 1)
              }}>Coba lagi</button>
            </div>
          )}
          {!loading && !loadError && (
            visibleProducts.length ? (
              <div className="table-scroll">
                <table>
                  <thead><tr><th scope="col">Produk</th><th scope="col">SKU</th><th scope="col">Harga</th><th scope="col">Stok</th><th scope="col">Status</th><th scope="col">Aksi</th></tr></thead>
                  <tbody>
                    {visibleProducts.map((product) => (
                      <tr key={product.id}>
                        <th scope="row">{product.name}</th>
                        <td>{product.sku || '—'}</td>
                        <td>{rupiah.format(product.price)}</td>
                        <td>{product.stock} {product.unit}</td>
                        <td><span className={product.is_active ? 'status active' : 'status'}>{product.is_active ? 'Aktif' : 'Nonaktif'}</span></td>
                        <td><button className="secondary" aria-label={'Ubah ' + product.name} disabled={Boolean(editor)} onClick={() => openEditor(product)}>Ubah</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="empty">{products.length ? 'Produk yang kamu cari tidak ditemukan.' : 'Belum ada produk. Tambahkan produk pertama untuk mengisi katalog.'}</p>
          )}
        </section>
      </main>
    </>
  )
}

export default App
