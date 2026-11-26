import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ReceiptPage from './ReceiptPage.jsx'

const path = window.location.pathname.replace(/\/$/, '')
const isProductsPage = path === '' || path === '/produk'
const isReceiptPage = isProductsPage || path === '/nota-baru'

if (isReceiptPage) document.title = (isProductsPage ? 'Produk dan Stok' : 'Buat Nota') + ' | Toko Indo Telur'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isReceiptPage ? <ReceiptPage initialView={isProductsPage ? 'products' : 'new'} /> : <App />}
  </StrictMode>,
)
