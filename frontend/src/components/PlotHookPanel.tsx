import { useState } from 'react'
import { createHook, updateHook, deleteHook } from '../api/client'

interface Props {
  hooks: any[]
  storyId: number
  onUpdate: () => void
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  active: { label: '活躍', color: 'text-yellow-400' },
  referenced: { label: '已引用', color: 'text-blue-400' },
  resolved: { label: '已解決', color: 'text-green-400' },
}

export default function PlotHookPanel({ hooks, storyId, onUpdate }: Props) {
  const [showAdd, setShowAdd] = useState(false)
  const [newDesc, setNewDesc] = useState('')

  const grouped = {
    active: hooks.filter((h) => h.status === 'active'),
    referenced: hooks.filter((h) => h.status === 'referenced'),
    resolved: hooks.filter((h) => h.status === 'resolved'),
  }

  const handleAdd = async () => {
    if (!newDesc.trim()) return
    await createHook(storyId, { description: newDesc, planted_episode: 0, status: 'active' })
    setNewDesc('')
    setShowAdd(false)
    onUpdate()
  }

  const handleStatusChange = async (id: number, newStatus: string) => {
    await updateHook(id, { status: newStatus })
    onUpdate()
  }

  const handleDelete = async (id: number) => {
    await deleteHook(id)
    onUpdate()
  }

  const renderGroup = (status: string, items: any[]) => {
    if (items.length === 0) return null
    const info = STATUS_LABELS[status]
    return (
      <div key={status}>
        <h4 className={`text-xs font-bold mb-2 ${info.color}`}>{info.label} ({items.length})</h4>
        {items.map((h) => (
          <div key={h.id} className="bg-novel-bg rounded border border-novel-border p-3 mb-2 text-sm">
            <p className="mb-2">{h.description}</p>
            <div className="flex items-center justify-between text-xs text-novel-muted">
              <span>
                埋入：第{h.planted_episode}集
                {h.referenced_episodes?.length > 0 && ` | 引用：第${h.referenced_episodes.join(', ')}集`}
              </span>
              <div className="flex gap-2">
                {status !== 'resolved' && (
                  <button
                    onClick={() => handleStatusChange(h.id, status === 'active' ? 'referenced' : 'resolved')}
                    className="hover:text-novel-accent transition"
                  >
                    {status === 'active' ? '→ 已引用' : '→ 已解決'}
                  </button>
                )}
                <button onClick={() => handleDelete(h.id)} className="hover:text-novel-accent transition">
                  刪除
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      {renderGroup('active', grouped.active)}
      {renderGroup('referenced', grouped.referenced)}
      {renderGroup('resolved', grouped.resolved)}

      {hooks.length === 0 && !showAdd && (
        <p className="text-novel-muted text-xs text-center py-4">（尚無伏筆，生成集數後自動偵測，也可手動新增）</p>
      )}

      {showAdd ? (
        <div className="bg-novel-bg rounded-lg border border-novel-accent p-3 space-y-2">
          <textarea
            placeholder="伏筆描述"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            rows={3}
            className="w-full bg-novel-card border border-novel-border rounded px-3 py-1.5 text-sm outline-none focus:border-novel-accent resize-none"
          />
          <div className="flex gap-2">
            <button onClick={handleAdd} className="flex-1 py-1.5 bg-novel-accent text-white rounded text-sm">新增</button>
            <button onClick={() => setShowAdd(false)} className="flex-1 py-1.5 bg-novel-border rounded text-sm">取消</button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowAdd(true)}
          className="w-full py-2 border border-dashed border-novel-border rounded text-sm text-novel-muted hover:border-novel-accent hover:text-novel-accent transition"
        >
          + 手動新增伏筆
        </button>
      )}
    </div>
  )
}
