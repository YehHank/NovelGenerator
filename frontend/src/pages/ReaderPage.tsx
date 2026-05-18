import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getStory, getEpisodes, getEpisode,
  getCharacters, getHooks,
  generateEpisodeStream, getSettings
} from '../api/client'
import CharacterPanel from '../components/CharacterPanel'
import PlotHookPanel from '../components/PlotHookPanel'
import TTSPlayer from '../components/TTSPlayer'

export default function ReaderPage() {
  const { storyId } = useParams()
  const sid = Number(storyId)

  const [story, setStory] = useState<any>(null)
  const [episodes, setEpisodes] = useState<any[]>([])
  const [currentEp, setCurrentEp] = useState<any>(null)
  const [characters, setCharacters] = useState<any[]>([])
  const [hooks, setHooks] = useState<any[]>([])
  const [ttsEnabled, setTtsEnabled] = useState(false)

  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [autoGenerating, setAutoGenerating] = useState(false)
  const [streamContent, setStreamContent] = useState('')
  const [direction, setDirection] = useState('')
  const [showSidebar, setShowSidebar] = useState(false)
  const [sidebarTab, setSidebarTab] = useState<'characters' | 'hooks'>('characters')
  const [showNav, setShowNav] = useState(false)
  const [showControls, setShowControls] = useState(true)

  const abortRef = useRef<AbortController | null>(null)
  const autoGeneratingRef = useRef(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const streamMetaRef = useRef<{ episode_id: number; episode_number: number } | null>(null)
  const streamChunksRef = useRef<string>('')


  const loadData = useCallback(async () => {
    const [s, eps, chars, hks, settings] = await Promise.all([
      getStory(sid),
      getEpisodes(sid),
      getCharacters(sid),
      getHooks(sid),
      getSettings(),
    ])
    setStory(s)
    setEpisodes(eps)
    setCharacters(chars)
    setHooks(hks)
    setTtsEnabled(!!settings.tts_enabled)
    return eps
  }, [sid])

  useEffect(() => {
    setLoading(true)
    loadData().then((eps) => {
      if (eps.length > 0) {
        setCurrentEp(eps[eps.length - 1])
      }
    }).finally(() => setLoading(false))
  }, [loadData])

  useEffect(() => {
    return () => {
      autoGeneratingRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  const navigateEp = async (epId: number) => {
    const ep = await getEpisode(epId)
    setCurrentEp(ep)
    contentRef.current?.scrollTo(0, 0)
  }

  const generateOnce = useCallback((directionHint: string) => {
    const activeDirection = directionHint.trim()
    setGenerating(true)
    setStreamContent('')
    streamMetaRef.current = null
    streamChunksRef.current = ''

    return new Promise<boolean>((resolve) => {
      let settled = false
      let controller: AbortController | null = null

      // 每 50ms 才把累積的 chunk flush 到 state，避免每個 chunk 觸發 re-render
      const flushTimer = setInterval(() => {
        setStreamContent(streamChunksRef.current)
      }, 50)

      const finish = (success: boolean) => {
        if (settled) return
        settled = true
        clearInterval(flushTimer)
        if (abortRef.current === controller) {
          abortRef.current = null
        }
        resolve(success)
      }

      controller = generateEpisodeStream(
        sid,
        activeDirection,
        // onChunk
        (chunk) => {
          streamChunksRef.current += chunk
        },
        // onMeta
        (meta) => {
          streamMetaRef.current = meta
        },
        // onDone
        async () => {
          // Immediately build a local episode from stream content so user never sees blank
          const meta = streamMetaRef.current
          const content = streamChunksRef.current
          if (meta && content) {
            const localEp = {
              id: meta.episode_id,
              story_id: sid,
              episode_number: meta.episode_number,
              title: `第${meta.episode_number}集`,
              content,
              summary: '',
              direction_hint: activeDirection,
              audio_path: '',
              created_at: new Date().toISOString(),
            }
            setCurrentEp(localEp)
            setEpisodes((prev) => [...prev.filter(e => e.id !== localEp.id), localEp])
          }
          setStreamContent('')
          setGenerating(false)
          setDirection('')

          try {
            const eps = await loadData()
            if (eps.length > 0) {
              const latest = eps[eps.length - 1]
              if (latest.content) {
                setCurrentEp(latest)
              }
            }
          } catch (e) {
            console.error('Background loadData failed after generation:', e)
          }

          finish(true)
        },
        // onError
        (err) => {
          if (controller?.signal.aborted) {
            setGenerating(false)
            finish(false)
            return
          }

          autoGeneratingRef.current = false
          setAutoGenerating(false)
          setGenerating(false)
          alert('生成失敗：' + err)
          finish(false)
        },
        // onAudio — 生成時不自動播放，由有聲書按鈕觸發
        undefined,
      )

      abortRef.current = controller
      controller.signal.addEventListener('abort', () => {
        setGenerating(false)
        finish(false)
      }, { once: true })
    })
  }, [loadData, sid])

  const handleGenerate = useCallback(() => {
    if (generating || autoGeneratingRef.current) return
    void generateOnce(direction)
  }, [direction, generateOnce, generating])

  const handleAutoGenerate = useCallback(() => {
    if (generating || autoGeneratingRef.current) return

    autoGeneratingRef.current = true
    setAutoGenerating(true)

    void (async () => {
      let nextDirection = direction

      while (autoGeneratingRef.current) {
        const success = await generateOnce(nextDirection)
        nextDirection = ''

        if (!success) {
          break
        }
      }

      autoGeneratingRef.current = false
      setAutoGenerating(false)
    })()
  }, [direction, generateOnce, generating])

  const handleStopAuto = useCallback(() => {
    autoGeneratingRef.current = false
    setAutoGenerating(false)
  }, [])

  const handleStop = () => {
    autoGeneratingRef.current = false
    setAutoGenerating(false)
    abortRef.current?.abort()
    setGenerating(false)
  }

  const currentIndex = episodes.findIndex((e) => e.id === currentEp?.id)
  const prevEp = currentIndex > 0 ? episodes[currentIndex - 1] : null
  const nextEp = currentIndex < episodes.length - 1 ? episodes[currentIndex + 1] : null

  if (loading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-novel-bg gap-4">
        <div className="w-10 h-10 border-4 border-novel-border border-t-novel-accent rounded-full animate-spin" />
        <p className="text-novel-muted text-lg">正在載入故事…</p>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-novel-card border-b border-novel-border px-3 sm:px-4 py-2 sm:py-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <Link to="/" className="text-novel-accent hover:opacity-80 transition font-bold shrink-0">
              ← 書庫
            </Link>
            <h1 className="text-base sm:text-lg font-semibold truncate">{story?.title}</h1>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <span className="text-novel-muted text-xs sm:text-sm hidden sm:inline">共 {episodes.length} 集</span>
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 px-3 py-1 bg-novel-border rounded text-sm hover:bg-novel-accent transition flex items-center justify-center"
            >
              <span className="hidden sm:inline">{showSidebar ? '收起面板' : '角色/伏筆'}</span>
              <span className="sm:hidden">📋</span>
            </button>
          </div>
        </div>
        {/* Mobile episode info */}
        {currentEp && (
          <div className="sm:hidden text-novel-muted text-xs mt-1 flex items-center justify-between">
            <span>第 {currentEp.episode_number} 集 — {currentEp.title}</span>
            <span>共 {episodes.length} 集</span>
          </div>
        )}
        {/* Desktop episode info */}
        {currentEp && (
          <span className="text-novel-muted text-sm hidden sm:block mt-1">第 {currentEp.episode_number} 集 — {currentEp.title}</span>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Main content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Episode content */}
          <div ref={contentRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 sm:py-8 max-w-3xl mx-auto w-full">
            {(generating || (!currentEp && !!streamContent)) && streamContent ? (
              <div className="novel-prose whitespace-pre-wrap">{streamContent}<span className="animate-pulse text-novel-accent">▌</span></div>
            ) : currentEp ? (
              <div className="novel-prose whitespace-pre-wrap">{currentEp.content}</div>
            ) : (
              <div className="text-center text-novel-muted py-12 sm:py-20">
                <p className="text-xl sm:text-2xl mb-4">還沒有任何集數</p>
                <p className="text-sm sm:text-base">在下方輸入方向提示（可選），然後點擊「生成下一集」開始吧！</p>
              </div>
            )}
          </div>

          {/* Navigation + TTS (collapsible on mobile) */}
          {currentEp && !generating && (
            <div className="border-t border-novel-border shrink-0">
              {/* Mobile toggle bar */}
              <button
                onClick={() => setShowNav(!showNav)}
                className="sm:hidden w-full flex items-center justify-center gap-2 py-2 text-xs text-novel-muted hover:text-novel-text transition"
              >
                <span>{showNav ? '收合導航 ▲' : '展開導航 ▼'}</span>
              </button>
              {/* Nav content - always visible on desktop, collapsible on mobile */}
              <div className={`${showNav ? 'block' : 'hidden'} sm:block px-3 sm:px-6 py-2 sm:py-3`}>
                {/* Desktop layout */}
                <div className="hidden sm:flex items-center justify-between">
                  <button
                    onClick={() => prevEp && navigateEp(prevEp.id)}
                    disabled={!prevEp}
                    className="px-4 py-2 bg-novel-border rounded disabled:opacity-30 hover:bg-novel-accent transition"
                  >
                    ← 上一集
                  </button>
                  <div className="flex items-center gap-3">
                    <label className="text-sm text-novel-muted whitespace-nowrap">快速選集</label>
                    <select
                      value={currentEp.id}
                      onChange={(e) => void navigateEp(Number(e.target.value))}
                      className="bg-novel-bg border border-novel-border rounded px-3 py-2 text-sm min-w-56 max-w-80 focus:border-novel-accent outline-none"
                    >
                      {episodes.map((episode) => (
                        <option key={episode.id} value={episode.id}>
                          第 {episode.episode_number} 集 - {episode.title}
                        </option>
                      ))}
                    </select>
                    {ttsEnabled ? <TTSPlayer episodeId={currentEp.id} /> : null}
                  </div>
                  <button
                    onClick={() => nextEp && navigateEp(nextEp.id)}
                    disabled={!nextEp}
                    className="px-4 py-2 bg-novel-border rounded disabled:opacity-30 hover:bg-novel-accent transition"
                  >
                    下一集 →
                  </button>
                </div>
                {/* Mobile layout */}
                <div className="sm:hidden space-y-2">
                  <select
                    value={currentEp.id}
                    onChange={(e) => void navigateEp(Number(e.target.value))}
                    className="w-full bg-novel-bg border border-novel-border rounded px-3 py-3 text-sm focus:border-novel-accent outline-none"
                  >
                    {episodes.map((episode) => (
                      <option key={episode.id} value={episode.id}>
                        第 {episode.episode_number} 集 - {episode.title}
                      </option>
                    ))}
                  </select>
                  <div className="flex gap-2">
                    <button
                      onClick={() => prevEp && navigateEp(prevEp.id)}
                      disabled={!prevEp}
                      className="flex-1 min-h-[44px] bg-novel-border rounded disabled:opacity-30 hover:bg-novel-accent transition text-sm"
                    >
                      ← 上一集
                    </button>
                    <button
                      onClick={() => nextEp && navigateEp(nextEp.id)}
                      disabled={!nextEp}
                      className="flex-1 min-h-[44px] bg-novel-border rounded disabled:opacity-30 hover:bg-novel-accent transition text-sm"
                    >
                      下一集 →
                    </button>
                  </div>
                  {ttsEnabled ? <TTSPlayer episodeId={currentEp.id} /> : null}
                </div>
              </div>
            </div>
          )}

          {/* Generation controls (collapsible on mobile) */}
          <div className="border-t border-novel-border shrink-0">
            {/* Mobile toggle bar */}
            <button
              onClick={() => setShowControls(!showControls)}
              className="sm:hidden w-full flex items-center justify-center gap-2 py-2 text-xs text-novel-muted hover:text-novel-text transition"
            >
              <span>{showControls ? '收合生成 ▲' : '展開生成 ▼'}</span>
            </button>
            {/* Controls content */}
            <div className={`${showControls ? 'block' : 'hidden'} sm:block px-3 sm:px-6 py-3 sm:py-4`}>
              {/* Desktop layout */}
              <div className="hidden sm:flex max-w-3xl mx-auto gap-3">
                <input
                  placeholder="本集方向提示（可選，例如：讓主角發現一個秘密通道）"
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  disabled={generating || autoGenerating}
                  className="flex-1 bg-novel-bg border border-novel-border rounded px-4 py-2 focus:border-novel-accent outline-none disabled:opacity-50"
                  onKeyDown={(e) => e.key === 'Enter' && !generating && !autoGenerating && handleGenerate()}
                />
                {autoGenerating ? (
                  <button
                    onClick={handleStopAuto}
                    className="px-6 py-2 bg-red-600 text-white rounded font-semibold hover:opacity-90 transition"
                  >
                    取消自動
                  </button>
                ) : generating ? (
                  <button
                    onClick={handleStop}
                    className="px-6 py-2 bg-red-600 text-white rounded font-semibold hover:opacity-90 transition"
                  >
                    停止
                  </button>
                ) : (
                  <>
                    <button
                      onClick={handleGenerate}
                      className="px-6 py-2 bg-novel-accent text-white rounded font-semibold hover:opacity-90 transition whitespace-nowrap"
                    >
                      生成下一集
                    </button>
                    <button
                      onClick={handleAutoGenerate}
                      className="px-6 py-2 bg-novel-card border border-novel-accent text-novel-accent rounded font-semibold hover:bg-novel-accent hover:text-white transition whitespace-nowrap"
                    >
                      自動生成
                    </button>
                  </>
                )}
              </div>
              {/* Mobile layout */}
              <div className="sm:hidden space-y-2">
                <input
                  placeholder="方向提示（可選）"
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  disabled={generating || autoGenerating}
                  className="w-full bg-novel-bg border border-novel-border rounded px-4 py-3 text-sm focus:border-novel-accent outline-none disabled:opacity-50"
                  onKeyDown={(e) => e.key === 'Enter' && !generating && !autoGenerating && handleGenerate()}
                />
                <div className="flex gap-2">
                  {autoGenerating ? (
                    <button
                      onClick={handleStopAuto}
                      className="flex-1 min-h-[44px] bg-red-600 text-white rounded font-semibold hover:opacity-90 transition text-sm"
                    >
                      取消自動
                    </button>
                  ) : generating ? (
                    <button
                      onClick={handleStop}
                      className="flex-1 min-h-[44px] bg-red-600 text-white rounded font-semibold hover:opacity-90 transition text-sm"
                    >
                      停止
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={handleGenerate}
                        className="flex-1 min-h-[44px] bg-novel-accent text-white rounded font-semibold hover:opacity-90 transition text-sm"
                      >
                        生成下一集
                      </button>
                      <button
                        onClick={handleAutoGenerate}
                        className="flex-1 min-h-[44px] bg-novel-card border border-novel-accent text-novel-accent rounded font-semibold hover:bg-novel-accent hover:text-white transition text-sm"
                      >
                        自動生成
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Sidebar - overlay on mobile, side panel on desktop */}
        {showSidebar && (
          <>
            {/* Mobile backdrop */}
            <div
              className="sm:hidden fixed inset-0 bg-black/50 z-40"
              onClick={() => setShowSidebar(false)}
            />
            <aside className="fixed inset-y-0 right-0 w-[85vw] max-w-sm sm:static sm:w-80 border-l border-novel-border bg-novel-card overflow-y-auto shrink-0 z-50">
              {/* Mobile close button */}
              <div className="sm:hidden flex items-center justify-between px-4 py-3 border-b border-novel-border">
                <span className="font-semibold">角色 / 伏筆</span>
                <button
                  onClick={() => setShowSidebar(false)}
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center text-lg hover:text-novel-accent transition"
                >
                  ✕
                </button>
              </div>
              <div className="flex border-b border-novel-border">
                <button
                  onClick={() => setSidebarTab('characters')}
                  className={`flex-1 py-3 min-h-[44px] text-sm font-semibold transition ${sidebarTab === 'characters' ? 'text-novel-accent border-b-2 border-novel-accent' : 'text-novel-muted hover:text-novel-text'}`}
                >
                  角色 ({characters.length})
                </button>
                <button
                  onClick={() => setSidebarTab('hooks')}
                  className={`flex-1 py-3 min-h-[44px] text-sm font-semibold transition ${sidebarTab === 'hooks' ? 'text-novel-accent border-b-2 border-novel-accent' : 'text-novel-muted hover:text-novel-text'}`}
                >
                  伏筆 ({hooks.length})
                </button>
              </div>
              {sidebarTab === 'characters' ? (
                <CharacterPanel characters={characters} storyId={sid} onUpdate={loadData} />
              ) : (
                <PlotHookPanel hooks={hooks} storyId={sid} onUpdate={loadData} />
              )}
            </aside>
          </>
        )}
      </div>
    </div>
  )
}
