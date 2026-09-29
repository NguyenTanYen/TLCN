import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ToastProvider } from './components/ui'
import './styles.css'
import './charts'

createRoot(document.getElementById('root')).render(
  <BrowserRouter><ToastProvider><App /></ToastProvider></BrowserRouter>
)
