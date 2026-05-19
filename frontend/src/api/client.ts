import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

// ── Stories ──
export const getStories = () => api.get('/stories').then(r => r.data);
export const getStory = (id: number) => api.get(`/stories/${id}`).then(r => r.data);
export const createStory = (data: any) => api.post('/stories', data).then(r => r.data);
export const updateStory = (id: number, data: any) => api.put(`/stories/${id}`, data).then(r => r.data);
export const deleteStory = (id: number) => api.delete(`/stories/${id}`);

// ── Episodes ──
export const getEpisodes = (storyId: number) => api.get(`/stories/${storyId}/episodes`).then(r => r.data);
export const getEpisode = (id: number) => api.get(`/episodes/${id}`).then(r => r.data);
export const generateEpisode = (storyId: number, directionHint = '') =>
  api.post(`/stories/${storyId}/episodes/generate`, { direction_hint: directionHint }).then(r => r.data);
export const reExtractEpisode = (episodeId: number) =>
  api.post(`/episodes/${episodeId}/re-extract`).then(r => r.data);

// SSE streaming generation
export function generateEpisodeStream(
  storyId: number,
  directionHint: string,
  onChunk: (chunk: string) => void,
  onMeta: (meta: { episode_id: number; episode_number: number }) => void,
  onDone: (title?: string) => Promise<void> | void,
  onError: (err: string) => void,
  onAudio?: (base64: string) => void,
): AbortController {
  const controller = new AbortController();
  fetch(`/api/stories/${storyId}/episodes/generate/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction_hint: directionHint }),
    signal: controller.signal,
  })
    .then(async (resp) => {
      if (!resp.ok) {
        onError(`HTTP ${resp.status}`);
        return;
      }
      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let doneReceived = false;
      let doneTitle: string | undefined = undefined;
      let streamError: string | null = null;

      const processLine = (line: string) => {
        if (!line.startsWith('data: ')) return;
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed.error) streamError = String(parsed.error);
          else if (parsed.episode_id) onMeta(parsed);
          else if (parsed.content) onChunk(parsed.content);
          else if (parsed.audio) onAudio?.(parsed.audio);
          else if (parsed.done) { doneReceived = true; doneTitle = parsed.title; }
        } catch { /* ignore malformed JSON */ }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          processLine(line);
        }
      }

      // Flush remaining buffer — the done event may be stuck here
      if (buffer.trim()) {
        processLine(buffer.trim());
      }

      if (streamError) {
        onError(streamError);
        return;
      }

      if (!doneReceived) {
        onError('生成中斷：伺服器未送出完成訊號');
        return;
      }

      try {
        await onDone(doneTitle);
      } catch (e) {
        onError(String(e));
      }
    })
    .catch((e) => {
      if (e.name !== 'AbortError') onError(String(e));
    });
  return controller;
}

// ── Characters ──
export const getCharacters = (storyId: number) => api.get(`/stories/${storyId}/characters`).then(r => r.data);
export const createCharacter = (storyId: number, data: any) => api.post(`/stories/${storyId}/characters`, data).then(r => r.data);
export const updateCharacter = (id: number, data: any) => api.put(`/characters/${id}`, data).then(r => r.data);
export const deleteCharacter = (id: number) => api.delete(`/characters/${id}`);

// ── Plot Hooks ──
export const getHooks = (storyId: number, status?: string) => {
  const params = status ? { status } : {};
  return api.get(`/stories/${storyId}/hooks`, { params }).then(r => r.data);
};
export const createHook = (storyId: number, data: any) => api.post(`/stories/${storyId}/hooks`, data).then(r => r.data);
export const updateHook = (id: number, data: any) => api.put(`/hooks/${id}`, data).then(r => r.data);
export const deleteHook = (id: number) => api.delete(`/hooks/${id}`);

// ── TTS ──
export const getEpisodeAudioUrl = (episodeId: number) => `/api/episodes/${episodeId}/audio`;

// ── Settings ──
export const getSettings = () => api.get('/settings').then(r => r.data);
export const updateSettings = (data: any) => api.put('/settings', data).then(r => r.data);

// ── Export ──
export const getExportPdfUrl = (storyId: number) => `/api/stories/${storyId}/export/pdf`;
