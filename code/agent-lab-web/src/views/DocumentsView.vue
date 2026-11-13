<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import {
  NDataTable, NButton, NSpace, NTag, NUpload, NInput, NPopconfirm, NModal,
  NResult, NSpin, NEmpty, NPagination,
  useMessage, type DataTableColumns, type UploadFileInfo,
} from 'naive-ui'

interface DocRow {
  id: string; title: string; source: string; doc_type: string
  char_count: number; chunk_count: number; created_at: string
}

interface PreviewChunk {
  chunk_index: number
  heading: string
  text: string
}

const docs = ref<DocRow[]>([])
const loading = ref(true)
const uploading = ref(false)
const keyword = ref('')
const message = useMessage()

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return docs.value
  return docs.value.filter(d =>
    `${d.title || ''} ${d.source || ''}`.toLowerCase().includes(k),
  )
})

// ---- 预览 ----
const previewOpen = ref(false)
const previewDocId = ref('')
const previewTitle = ref('')
const previewLoading = ref(false)
const previewChunks = ref<PreviewChunk[]>([])
const previewTotal = ref(0)
const previewPage = ref(1)
const PREVIEW_SIZE = 10

/**
 * 预览按页拉取而不是一次性全拿。
 * 一个 500 块的文档全量返回可能几 MB，而用户通常只看前几块判断"传对没有"。
 */
async function loadPreviewChunks(docId: string, page: number) {
  previewLoading.value = true
  try {
    const offset = (page - 1) * PREVIEW_SIZE
    const res = await fetch(
      `/api/v1/rag/documents/${docId}/chunks?limit=${PREVIEW_SIZE}&offset=${offset}`,
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json() as { chunks: PreviewChunk[] }
    previewChunks.value = data.chunks
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载片段失败')
    previewChunks.value = []
  } finally {
    previewLoading.value = false
  }
}

function openPreview(row: DocRow) {
  previewDocId.value = row.id
  previewTitle.value = row.title || row.source
  previewTotal.value = row.chunk_count
  previewPage.value = 1
  previewChunks.value = []
  previewOpen.value = true
  void loadPreviewChunks(row.id, 1)
}

function onPreviewPageChange(page: number) {
  previewPage.value = page
  void loadPreviewChunks(previewDocId.value, page)
}

// ---- 列表 ----
const columns: DataTableColumns<DocRow> = [
  {
    title: '文件名', key: 'source', ellipsis: { tooltip: true }, minWidth: 180,
    render(r) {
      return h(
        NButton,
        { text: true, onClick: () => openPreview(r) },
        { default: () => r.source },
      )
    },
  },
  {
    title: '类型', key: 'doc_type', width: 60,
    // 子内容必须用函数插槽；直接传字符串会让 Naive UI 报
    // "Non-function value encountered for default slot"
    render(r) {
      return h(NTag, { size: 'tiny', bordered: false }, { default: () => r.doc_type })
    },
  },
  { title: '字数', key: 'char_count', width: 80, render(r) { return r.char_count.toLocaleString() } },
  { title: '片段', key: 'chunk_count', width: 60 },
  {
    title: '索引时间', key: 'created_at', width: 120,
    render(r) { return r.created_at.slice(0, 16).replace('T', ' ') },
  },
  {
    title: '操作', key: 'actions', width: 120,
    render(r) {
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { size: 'tiny', quaternary: true, onClick: () => openPreview(r) },
            { default: () => '预览' }),
          // 删文档会连带删掉全部向量，重传要重新 embedding，必须确认
          h(NPopconfirm, { onPositiveClick: () => removeDoc(r.id) }, {
            trigger: () => h(NButton, { size: 'tiny', quaternary: true },
              { default: () => '删除' }),
            default: () => `删除《${r.title || r.source}》及其 ${r.chunk_count} 个片段？重新索引需要重新计算向量。`,
          }),
        ],
      })
    },
  },
]

async function fetchDocs() {
  loading.value = true
  try {
    const res = await fetch('/api/v1/rag/documents')
    docs.value = await res.json()
  } finally {
    loading.value = false
  }
}

async function removeDoc(id: string) {
  try {
    const res = await fetch(`/api/v1/rag/documents/${id}`, { method: 'DELETE' })
    if (!res.ok && res.status !== 404) {
      const err = await res.json().catch(() => ({}))
      throw new Error((err as { message?: string }).message || `删除失败（${res.status}）`)
    }
    docs.value = docs.value.filter(d => d.id !== id)
    message.success('已删除')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '删除失败')
  }
}

async function handleUpload({ file }: { file: UploadFileInfo }) {
  if (!file.file) return
  uploading.value = true
  const form = new FormData()
  form.append('file', file.file)
  try {
    const resp = await fetch('/api/v1/rag/upload', { method: 'POST', body: form })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error((err as { message?: string }).message || `HTTP ${resp.status}`)
    }
    const data = await resp.json()
    message.success(`《${data.title ?? file.name}》已索引，${data.chunks ?? 0} 个片段`)
    await fetchDocs()
  } catch (e) {
    message.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

onMounted(fetchDocs)
</script>

<template>
  <div>
    <div class="doc-header">
      <h2>文档管理</h2>
      <NSpace>
        <NInput
          v-model:value="keyword"
          placeholder="搜索文件名"
          clearable
          size="small"
          style="width: 200px"
        />
        <NUpload
          :show-file-list="false"
          accept=".md,.txt,.pdf"
          :disabled="uploading"
          @change="handleUpload"
        >
          <NButton type="primary" size="small" :loading="uploading">
            {{ uploading ? '索引中…' : '上传文档' }}
          </NButton>
        </NUpload>
        <NButton size="small" quaternary @click="fetchDocs">刷新</NButton>
      </NSpace>
    </div>

    <NResult
      v-if="!loading && docs.length === 0"
      status="info"
      title="还没有文档"
      description="上传 md/txt/pdf 文档构建知识库"
      size="small"
    />

    <NResult
      v-else-if="!loading && filtered.length === 0"
      status="info"
      title="没有匹配的文档"
      :description="`没有文件名包含「${keyword}」的文档`"
      size="small"
    />

    <NSpin v-if="loading" />

    <NDataTable
      v-if="filtered.length"
      :columns="columns"
      :data="filtered"
      :bordered="false"
      :single-line="false"
      size="small"
      :scroll-x="720"
      class="doc-table"
    />

    <!-- 预览：确认「传进来的到底是什么」 -->
    <NModal
      v-model:show="previewOpen"
      preset="card"
      :title="`片段预览 · ${previewTitle}`"
      style="width: min(820px, 92vw)"
    >
      <NSpin v-if="previewLoading" />
      <NEmpty v-else-if="previewChunks.length === 0" description="没有片段" />
      <template v-else>
        <div v-for="c in previewChunks" :key="c.chunk_index" class="chunk">
          <div class="chunk__head">
            片段 {{ c.chunk_index + 1 }}
            <span v-if="c.heading" class="chunk__heading">{{ c.heading }}</span>
          </div>
          <pre class="chunk__text">{{ c.text }}</pre>
        </div>
        <NPagination
          v-if="previewTotal > 10"
          :page="previewPage"
          :page-count="Math.ceil(previewTotal / 10)"
          size="small"
          class="chunk__pager"
          @update:page="onPreviewPageChange"
        />
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.doc-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.doc-header h2 { margin: 0; font-size: 18px; color: #e2e8f0; }
.doc-table { margin-top: 12px; }

.chunk { margin-bottom: 14px; }
.chunk__head {
  font-size: 12px; color: #2dd4bf; margin-bottom: 6px;
}
.chunk__heading { color: rgba(255, 255, 255, 0.45); margin-left: 8px; }
.chunk__text {
  margin: 0;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.65;
  color: rgba(255, 255, 255, 0.78);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow-y: auto;
}
.chunk__pager { margin-top: 12px; justify-content: center; }
</style>
