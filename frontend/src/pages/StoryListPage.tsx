import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { getStories, createStory } from '../api/client'

export default function StoryListPage() {
  const [stories, setStories] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ title: '', genre: '', world_setting: '', writing_style: '' })
  const navigate = useNavigate()

  const load = () => getStories().then(setStories)
  useEffect(() => { setLoading(true); load().finally(() => setLoading(false)) }, [])

  const handleCreate = async () => {
    if (!form.title.trim()) return
    const s = await createStory(form)
    setShowCreate(false)
    setForm({ title: '', genre: '', world_setting: '', writing_style: '' })
    navigate(`/story/${s.id}`)
  }

  if (loading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-novel-bg gap-4">
        <div className="w-10 h-10 border-4 border-novel-border border-t-novel-accent rounded-full animate-spin" />
        <p className="text-novel-muted text-lg">正在載入書庫…</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:p-6 py-4">
      <div className="flex items-center justify-between mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold">
          <span className="text-novel-accent">Novel</span>Generator
        </h1>
        <Link to="/settings" className="min-h-[44px] min-w-[44px] flex items-center justify-center text-novel-muted hover:text-novel-text transition">
          ⚙ 設定
        </Link>
      </div>

      <div className="grid gap-3 sm:gap-4">
        {stories.map((s) => (
          <div
            key={s.id}
            className="bg-novel-card border border-novel-border rounded-lg p-4 sm:p-5 flex justify-between items-center hover:border-novel-accent active:border-novel-accent transition cursor-pointer min-h-[60px]"
            onClick={() => navigate(`/story/${s.id}`)}
          >
            <div>
              <h2 className="text-lg sm:text-xl font-semibold">{s.title}</h2>
              <p className="text-novel-muted text-xs sm:text-sm mt-1">
                {s.genre && <span className="mr-3">📚 {s.genre}</span>}
                <span>📖 {s.episode_count} 集</span>
              </p>
            </div>
          </div>
        ))}

        {stories.length === 0 && !showCreate && (
          <p className="text-novel-muted text-center py-12">還沒有任何小說，建立一部吧！</p>
        )}
      </div>

      {!showCreate ? (
        <button
          onClick={() => setShowCreate(true)}
          className="mt-6 w-full py-3 bg-novel-accent text-white rounded-lg font-semibold hover:opacity-90 transition"
        >
          + 建立新小說
        </button>
      ) : (
        <div className="mt-6 bg-novel-card border border-novel-border rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold">建立新小說</h3>
          <input
            placeholder="小說標題"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none"
          />
          <input
            placeholder="類型（如：玄幻、科幻、都市）"
            value={form.genre}
            onChange={(e) => setForm({ ...form, genre: e.target.value })}
            className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none"
          />
          <textarea
            placeholder="世界觀設定（可選，愈詳細角色與劇情愈一致）"
            value={form.world_setting}
            onChange={(e) => setForm({ ...form, world_setting: e.target.value })}
            rows={4}
            className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none resize-none"
          />
          <textarea
            placeholder="寫作風格（可選，如：金庸風、輕小說風、硬科幻風）"
            value={form.writing_style}
            onChange={(e) => setForm({ ...form, writing_style: e.target.value })}
            rows={2}
            className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none resize-none"
          />
          <div className="flex gap-3">
            <button
              onClick={handleCreate}
              className="flex-1 min-h-[44px] py-2 bg-novel-accent text-white rounded font-semibold hover:opacity-90 transition"
            >
              建立
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="flex-1 min-h-[44px] py-2 bg-novel-border text-novel-muted rounded hover:text-novel-text transition"
            >
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
