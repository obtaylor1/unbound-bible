import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './auth/AuthProvider.jsx'
import PublicStudyPage from './sharing/PublicStudyPage.jsx'
import { shareIdFromPath } from './routing/pageRoutes.js'

const sharedStudyId = shareIdFromPath(window.location.pathname)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {sharedStudyId ? <PublicStudyPage shareId={sharedStudyId} /> : <AuthProvider><App /></AuthProvider>}
  </StrictMode>,
)
