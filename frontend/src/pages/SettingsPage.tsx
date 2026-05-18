import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getSettings, updateSettings } from '../api/client'

export default function SettingsPage() {
  const [form, setForm] = useState<any>({})
  const [apiKey, setApiKey] = useState('')
  const [ttsApiKey, setTtsApiKey] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getSettings().then(setForm)
  }, [])

  const handleSave = async () => {
    const data: any = { ...form }
    if (apiKey) data.llm_api_key = apiKey
    if (ttsApiKey) data.tts_api_key = ttsApiKey
    await updateSettings(data)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const field = (label: string, key: string, type = 'text') => (
    <div>
      <label className="block text-sm text-novel-muted mb-1">{label}</label>
      <input
        type={type}
        value={form[key] ?? ''}
        onChange={(e) => setForm({ ...form, [key]: type === 'number' ? Number(e.target.value) : e.target.value })}
        className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none"
      />
    </div>
  )

  return (
    <div className="max-w-2xl mx-auto px-4 sm:p-6 py-4">
      <div className="flex items-center gap-4 mb-6 sm:mb-8">
        <Link to="/" className="min-h-[44px] min-w-[44px] flex items-center justify-center text-novel-accent hover:opacity-80 transition font-bold">← 返回</Link>
        <h1 className="text-xl sm:text-2xl font-bold">設定</h1>
      </div>

      <div className="space-y-6">
        <section className="bg-novel-card border border-novel-border rounded-lg p-4 sm:p-6 space-y-4">
          <h2 className="text-lg font-semibold text-novel-accent">LLM 設定</h2>
          {field('API Base URL', 'llm_base_url')}
          <div>
            <label className="block text-sm text-novel-muted mb-1">API Key</label>
            <input
              type="password"
              placeholder="(不顯示，輸入新值以更新)"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none"
            />
          </div>
          {field('模型名稱', 'llm_model')}
          {field('Temperature', 'temperature', 'number')}
          {field('Max Tokens', 'max_tokens', 'number')}
        </section>

        <section className="bg-novel-card border border-novel-border rounded-lg p-4 sm:p-6 space-y-4">
          <h2 className="text-lg font-semibold text-novel-accent">Context 設定</h2>
          {field('完整保留最近 N 集', 'context_full_episodes', 'number')}
          {field('摘要保留最近 N 集', 'context_summary_episodes', 'number')}
        </section>

        <section className="bg-novel-card border border-novel-border rounded-lg p-4 sm:p-6 space-y-4">
          <h2 className="text-lg font-semibold text-novel-accent">TTS 設定（有聲書）</h2>
          <div className="flex items-center gap-3">
            <label className="text-sm text-novel-muted">啟用 TTS</label>
            <button
              onClick={() => setForm({ ...form, tts_enabled: !form.tts_enabled })}
              className={`w-12 h-6 rounded-full transition ${form.tts_enabled ? 'bg-novel-accent' : 'bg-novel-border'} relative`}
            >
              <span className={`block w-5 h-5 bg-white rounded-full absolute top-0.5 transition ${form.tts_enabled ? 'left-6' : 'left-0.5'}`} />
            </button>
          </div>
          {form.tts_enabled && (
            <>
              {field('Fish Audio API URL', 'fishaudio_url')}
              <div>
                <label className="block text-sm text-novel-muted mb-1">Fish Audio API Key</label>
                <input
                  type="password"
                  placeholder="(不顯示，輸入新值以更新)"
                  value={ttsApiKey}
                  onChange={(e) => setTtsApiKey(e.target.value)}
                  className="w-full bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none"
                />
              </div>
              {field('Reference ID（聲音）', 'fishaudio_reference_id')}
              {field('Chunk Length', 'fishaudio_chunk_length', 'number')}
              {field('Max New Tokens', 'fishaudio_max_new_tokens', 'number')}
            </>
          )}
        </section>

        <button
          onClick={handleSave}
          className="w-full min-h-[48px] py-3 bg-novel-accent text-white rounded-lg font-semibold hover:opacity-90 transition"
        >
          {saved ? '✓ 已儲存' : '儲存設定'}
        </button>
      </div>
    </div>
  )
}
