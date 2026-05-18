import { Routes, Route, Navigate } from 'react-router-dom'
import StoryListPage from './pages/StoryListPage'
import ReaderPage from './pages/ReaderPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <div className="min-h-screen bg-novel-bg text-novel-text">
      <Routes>
        <Route path="/" element={<StoryListPage />} />
        <Route path="/story/:storyId" element={<ReaderPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </div>
  )
}
