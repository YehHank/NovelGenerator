import { useState } from 'react'
import { createCharacter, updateCharacter, deleteCharacter } from '../api/client'

interface Props {
  characters: any[]
  storyId: number
  onUpdate: () => void
}

export default function CharacterPanel({ characters, storyId, onUpdate }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [editingState, setEditingState] = useState<{ id: number; key: string; value: string } | null>(null)

  const handleAdd = async () => {
    if (!newName.trim()) return
    await createCharacter(storyId, { name: newName, description: newDesc })
    setNewName('')
    setNewDesc('')
    setShowAdd(false)
    onUpdate()
  }

  const handleDelete = async (id: number) => {
    if (!confirm('確定刪除此角色？')) return
    await deleteCharacter(id)
    onUpdate()
  }

  const handleStateUpdate = async (charId: number, currentState: any) => {
    if (!editingState) return
    const updated = { ...currentState, [editingState.key]: editingState.value }
    await updateCharacter(charId, { current_state: updated })
    setEditingState(null)
    onUpdate()
  }

  return (
    <div className="p-4 space-y-3">
      {characters.map((c) => (
        <div key={c.id} className="bg-novel-bg rounded-lg border border-novel-border">
          <div
            className="px-4 py-3 flex justify-between items-center cursor-pointer hover:bg-novel-border/30 transition"
            onClick={() => setExpanded(expanded === c.id ? null : c.id)}
          >
            <span className="font-semibold">{c.name}</span>
            <span className="text-novel-muted text-xs">{expanded === c.id ? '▲' : '▼'}</span>
          </div>

          {expanded === c.id && (
            <div className="px-4 pb-4 space-y-2 text-sm">
              {c.description && <p className="text-novel-muted">{c.description}</p>}

              {/* Current state */}
              <div>
                <h4 className="text-novel-accent text-xs font-bold mb-1">目前狀態</h4>
                {Object.entries(c.current_state || {}).map(([k, v]) => (
                  <div key={k} className="flex gap-2 items-center py-0.5">
                    <span className="text-novel-muted min-w-[4rem]">{k}:</span>
                    {editingState !== null && editingState.id === c.id && editingState.key === k ? (
                      <input
                        autoFocus
                        value={editingState.value}
                        onChange={(e) => setEditingState({ id: editingState.id, key: editingState.key, value: e.target.value })}
                        onBlur={() => handleStateUpdate(c.id, c.current_state)}
                        onKeyDown={(e) => e.key === 'Enter' && handleStateUpdate(c.id, c.current_state)}
                        className="flex-1 bg-novel-card border border-novel-accent rounded px-2 py-0.5 text-xs outline-none"
                      />
                    ) : (
                      <span
                        className="cursor-pointer hover:text-novel-accent transition"
                        onClick={() => setEditingState({ id: c.id, key: k, value: String(v) })}
                      >
                        {String(v)}
                      </span>
                    )}
                  </div>
                ))}
                {Object.keys(c.current_state || {}).length === 0 && (
                  <p className="text-novel-muted text-xs">（尚無狀態資料，生成集數後自動填入）</p>
                )}
              </div>

              {/* Traits */}
              {Object.keys(c.traits || {}).length > 0 && (
                <div>
                  <h4 className="text-novel-accent text-xs font-bold mb-1">特質</h4>
                  {Object.entries(c.traits).map(([k, v]) => (
                    <div key={k} className="py-0.5">
                      <span className="text-novel-muted">{k}: </span><span>{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={() => handleDelete(c.id)}
                className="text-xs text-novel-muted hover:text-novel-accent transition mt-2"
              >
                刪除角色
              </button>
            </div>
          )}
        </div>
      ))}

      {showAdd ? (
        <div className="bg-novel-bg rounded-lg border border-novel-accent p-3 space-y-2">
          <input
            placeholder="角色名稱"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full bg-novel-card border border-novel-border rounded px-3 py-1.5 text-sm outline-none focus:border-novel-accent"
          />
          <input
            placeholder="描述（可選）"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="w-full bg-novel-card border border-novel-border rounded px-3 py-1.5 text-sm outline-none focus:border-novel-accent"
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
          + 手動新增角色
        </button>
      )}
    </div>
  )
}
