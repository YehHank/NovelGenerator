import { useState, useRef, useEffect, useCallback, type MouseEvent, type TouchEvent } from 'react'
import { getEpisodeAudioUrl } from '../api/client'

interface Props {
  episodeId: number
}

function formatTime(sec: number) {
  if (!isFinite(sec) || isNaN(sec)) return '--:--'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function TTSPlayer({ episodeId }: Props) {
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showBar, setShowBar] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [bufferedEnd, setBufferedEnd] = useState(0)
  const [realDuration, setRealDuration] = useState(0) // 0 = unknown yet
  const [fullyLoaded, setFullyLoaded] = useState(false)
  const [dragging, setDragging] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const barRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef<number>(0)

  // The "effective duration" shown on the bar:
  // - If fully loaded & real duration known → real duration
  // - Otherwise → buffered end (grows as data streams in)
  const displayDuration = fullyLoaded && realDuration > 0 ? realDuration : bufferedEnd

  // Sync time & buffer from audio element
  const syncTime = useCallback(() => {
    const audio = audioRef.current
    if (audio) {
      if (!dragging) setCurrentTime(audio.currentTime)

      // Update buffered end
      if (audio.buffered.length > 0) {
        const end = audio.buffered.end(audio.buffered.length - 1)
        setBufferedEnd(end)
      }

      // Check if real duration is now known (finite)
      const dur = audio.duration
      if (isFinite(dur) && dur > 0) {
        setRealDuration(dur)
      }
    }
    rafRef.current = requestAnimationFrame(syncTime)
  }, [dragging])

  useEffect(() => {
    rafRef.current = requestAnimationFrame(syncTime)
    return () => cancelAnimationFrame(rafRef.current)
  }, [syncTime])

  // Cleanup audio on unmount or episodeId change
  useEffect(() => {
    return () => {
      audioRef.current?.pause()
      audioRef.current = null
      setShowBar(false)
      setPlaying(false)
      setFullyLoaded(false)
      setRealDuration(0)
      setBufferedEnd(0)
      setCurrentTime(0)
    }
  }, [episodeId])

  const createAudio = () => {
    const audio = new Audio(`${getEpisodeAudioUrl(episodeId)}?v=${Date.now()}`)
    audioRef.current = audio

    audio.onloadedmetadata = () => {
      if (isFinite(audio.duration) && audio.duration > 0) {
        setRealDuration(audio.duration)
        setFullyLoaded(true)
      }
    }

    // Fires when the browser estimates it can play through without buffering
    audio.oncanplaythrough = () => {
      if (isFinite(audio.duration) && audio.duration > 0) {
        setRealDuration(audio.duration)
        setFullyLoaded(true)
      }
    }

    // Also listen to 'progress' to update buffer info
    audio.onprogress = () => {
      if (audio.buffered.length > 0) {
        const end = audio.buffered.end(audio.buffered.length - 1)
        setBufferedEnd(end)
      }
      // If duration becomes finite, mark fully loaded
      if (isFinite(audio.duration) && audio.duration > 0) {
        setRealDuration(audio.duration)
      }
    }

    audio.onended = () => {
      audioRef.current = null
      setPlaying(false)
      setCurrentTime(0)
      setFullyLoaded(false)
      setRealDuration(0)
      setBufferedEnd(0)
      setShowBar(false)
    }

    audio.onerror = () => {
      audioRef.current = null
      setLoading(false)
      setPlaying(false)
      setShowBar(false)
      setFullyLoaded(false)
      setRealDuration(0)
      setBufferedEnd(0)
      setCurrentTime(0)
    }

    return audio
  }

  const toggle = () => {
    if (playing) {
      audioRef.current?.pause()
      setPlaying(false)
      return
    }

    // Already have an audio element → just resume
    if (audioRef.current) {
      audioRef.current.play()
      setPlaying(true)
      setShowBar(true)
      return
    }

    // First click: create audio and start playing
    setLoading(true)
    const audio = createAudio()

    audio.oncanplay = () => {
      setLoading(false)
      setPlaying(true)
      setShowBar(true)
      audio.play()
      // Clear this one-time handler so it doesn't fire again
      audio.oncanplay = null
    }
  }

  const seekFromEvent = (e: MouseEvent | TouchEvent) => {
    const bar = barRef.current
    const audio = audioRef.current
    if (!bar || !audio || displayDuration <= 0) return
    const rect = bar.getBoundingClientRect()
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))

    // If not fully loaded, clamp seek to buffered region
    let seekTo = ratio * displayDuration
    if (!fullyLoaded && audio.buffered.length > 0) {
      const maxSeek = audio.buffered.end(audio.buffered.length - 1) - 0.5
      seekTo = Math.min(seekTo, Math.max(0, maxSeek))
    }

    audio.currentTime = seekTo
    setCurrentTime(seekTo)
  }

  const handlePointerDown = (e: MouseEvent | TouchEvent) => {
    setDragging(true)
    seekFromEvent(e)
  }

  const handlePointerMove = (e: MouseEvent | TouchEvent) => {
    if (!dragging) return
    seekFromEvent(e)
  }

  const handlePointerUp = () => {
    setDragging(false)
  }

  const progress = displayDuration > 0 ? (currentTime / displayDuration) * 100 : 0
  // Buffer bar: if we know realDuration, show buffered relative to it; otherwise 100%
  const bufferPercent =
    fullyLoaded ? 100
    : realDuration > 0 ? (bufferedEnd / realDuration) * 100
    : 100

  return (
    <div className="flex w-full min-w-0 flex-col gap-1 sm:w-auto">
      <button
        onClick={toggle}
        disabled={loading}
        className="min-h-[44px] w-full px-4 py-2 bg-novel-border rounded hover:bg-novel-accent transition text-sm disabled:opacity-50 sm:w-auto"
        title="播放有聲書（需啟用 TTS）"
      >
        {loading ? '生成中...' : playing ? '⏸ 暫停' : '🔊 有聲書'}
      </button>

      {showBar && (
        <div className="flex w-full min-w-0 items-center gap-2 sm:min-w-[260px]">
          <span className="text-[10px] text-novel-muted w-9 text-right shrink-0">{formatTime(currentTime)}</span>
          <div
            ref={barRef}
            className="relative flex-1 min-w-0 h-8 flex items-center cursor-pointer touch-none select-none"
            onMouseDown={handlePointerDown}
            onMouseMove={handlePointerMove}
            onMouseUp={handlePointerUp}
            onMouseLeave={handlePointerUp}
            onTouchStart={handlePointerDown}
            onTouchMove={handlePointerMove}
            onTouchEnd={handlePointerUp}
          >
            {/* Track background */}
            <div className="absolute left-0 right-0 h-1.5 bg-novel-border rounded-full" />
            {/* Buffer fill (lighter) */}
            <div
              className="absolute left-0 h-1.5 bg-novel-muted/30 rounded-full transition-[width] duration-300"
              style={{ width: `${bufferPercent}%` }}
            />
            {/* Playback fill */}
            <div
              className="absolute left-0 h-1.5 bg-novel-accent rounded-full"
              style={{ width: `${progress}%` }}
            />
            {/* Thumb */}
            <div
              className="absolute w-4 h-4 bg-novel-accent rounded-full shadow-md -translate-x-1/2 transition-[left] duration-75"
              style={{ left: `${progress}%` }}
            />
          </div>
          <span className="text-[10px] text-novel-muted w-9 shrink-0">
            {fullyLoaded ? formatTime(realDuration) : `~${formatTime(bufferedEnd)}`}
          </span>
        </div>
      )}
    </div>
  )
}
