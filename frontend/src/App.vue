<script setup lang="ts">
import { ref, computed } from 'vue'
import Sidebar from './components/Sidebar.vue'
import MainCanvas from './components/MainCanvas.vue'
import ImageSlider from './components/ImageSlider.vue'
import { Image as ImageIcon } from 'lucide-vue-next'

const files = ref<{ path: string, status: string, progress: number, resultPath?: string }[]>([])
const processing = ref(false)
const selectedIndex = ref<number | null>(null)
const bboxes = ref<{ x: number, y: number, w: number, h: number }[]>([])
const outputDir = ref(localStorage.getItem('delogo_output_dir') || '/tmp/delogo_out')
const currentJobId = ref<string | null>(null)
const engineState = ref<'idle'|'warming'|'processing'>('idle')

const updateOutputDir = (dir: string) => {
  outputDir.value = dir
  localStorage.setItem('delogo_output_dir', dir)
}

const removeFile = (idx: number) => {
  files.value.splice(idx, 1)
  if (selectedIndex.value === idx) {
    selectedIndex.value = files.value.length > 0 ? 0 : null
  } else if (selectedIndex.value !== null && selectedIndex.value > idx) {
    selectedIndex.value--
  }
}

const clearAllFiles = () => {
  files.value = []
  selectedIndex.value = null
  bboxes.value = [] // Reset all masks for the new batch
}

const activeFile = computed(() => {
  if (selectedIndex.value === null || !files.value[selectedIndex.value]) return null
  return files.value[selectedIndex.value]
})

const handleDrop = (droppedFiles: FileList) => {
  for (let i = 0; i < droppedFiles.length; i++) {
    const file = droppedFiles[i] as any
    const actualPath = file.path || file.webkitRelativePath
    if (!actualPath) continue
    if (!files.value.find(f => f.path === actualPath)) {
      files.value.push({ path: actualPath, status: 'queued', progress: 0 })
    }
  }
  if (selectedIndex.value === null && files.value.length > 0) {
    selectedIndex.value = 0
  }
}

const startProcessing = async (targetFiles: typeof files.value) => {
  if (targetFiles.length === 0) return

  processing.value = true
  engineState.value = 'idle' // Will be updated by WS
  targetFiles.forEach(f => {
    f.status = 'queued'
    f.progress = 0
  })
  
  try {
    const res = await fetch("http://127.0.0.1:8000/api/v1/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        job_id: "job-" + Date.now(),
        input_files: targetFiles.map(f => f.path),
        output_dir: outputDir.value,
        bboxes: bboxes.value
      })
    })
    const data = await res.json()
    currentJobId.value = data.job_id
    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/progress/${data.job_id}`)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      // Ignore messages from older cancelled jobs
      if (msg.job_id !== currentJobId.value) return

      if (msg.status === 'starting_engine') {
        engineState.value = 'warming'
      } else if (msg.status === 'processing') {
        engineState.value = 'processing'
        const f = files.value.find(x => x.path.endsWith(msg.current_file))
        if (f) {
          f.status = 'processing'
          if (msg.progress !== undefined) f.progress = msg.progress
        }
      } else if (msg.status === 'file_done') {
        const f = files.value.find(x => x.path === msg.file)
        if (f) {
          f.status = 'completed'
          f.progress = 100
          f.resultPath = msg.result_path
        }
      } else if (msg.status === 'completed') {
        processing.value = false
        engineState.value = 'idle'
        ws.close()
      } else if (msg.status === 'error') {
        processing.value = false
        engineState.value = 'idle'
        alert(msg.message)
      } else if (msg.status === 'cancelled') {
        processing.value = false
        engineState.value = 'idle'
        files.value.forEach(f => {
          if (f.status === 'queued' || f.status === 'processing') {
            f.status = 'cancelled'
            f.progress = 0
          }
        })
        ws.close()
      }
    }
    ws.onerror = (e) => {
      console.error("WS Error", e)
      processing.value = false
      engineState.value = 'idle'
      alert("WebSocket connection error.")
    }
  } catch (err) {
    console.error(err)
    alert("Failed to start processing. Is the backend running?")
    processing.value = false
    engineState.value = 'idle'
  }
}

const triggerProcess = () => {
  const filesToProcess = files.value.filter(f => f.status === 'queued')
  if (filesToProcess.length === 0) {
    alert("All files have already been processed.")
    return
  }
  startProcessing(filesToProcess)
}

const triggerPreview = (file: any) => {
  if (!file) return
  startProcessing([file])
}

const cancelProcess = async () => {
  if (!currentJobId.value) return
  
  try {
    await fetch(`http://127.0.0.1:8000/api/v1/jobs/${currentJobId.value}/cancel`, {
      method: "POST"
    })
  } catch(e) {
    console.error("Failed to send cancel", e)
  }
  
  // Optimistically update UI
  processing.value = false
  engineState.value = 'idle'
  files.value.forEach(f => {
    if (f.status === 'queued' || f.status === 'processing') {
      f.status = 'cancelled'
      f.progress = 0
    }
  })
}

const reeditMask = (idx: number | null) => {
  if (idx === null || !files.value[idx]) return
  files.value[idx].status = 'queued'
  files.value[idx].progress = 0
}
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-900 text-slate-300 p-8 font-sans overflow-hidden">
    <h1 class="text-3xl font-bold mb-8 text-slate-50 flex items-center gap-3 shrink-0">
      <span class="bg-gradient-to-r from-cyan-400 to-purple-500 text-transparent bg-clip-text">Delogo</span>
      <span class="text-lg text-slate-500 font-normal">Batch Processor</span>
    </h1>

    <div class="flex flex-1 gap-8 min-h-0">
      <Sidebar 
        :files="files" 
        :processing="processing"
        :engine-state="engineState"
        :output-dir="outputDir"
        @drop="handleDrop"
        @start="triggerProcess"
        @select="(idx) => selectedIndex = idx"
        @update:output-dir="updateOutputDir"
        @remove="removeFile"
        @cancel="cancelProcess"
        @clearAll="clearAllFiles"
      />

      <div class="flex-1 rounded-2xl bg-slate-800/60 backdrop-blur-xl border border-slate-600/30 p-6 min-w-0 min-h-0 flex flex-col">
        <template v-if="activeFile">
          <!-- Top Toolbar -->
          <div class="flex justify-between items-center mb-4 shrink-0">
            <h2 class="text-slate-400 font-medium truncate text-sm flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
              {{ activeFile.path.split('/').pop() }}
            </h2>
            
            <div class="flex gap-3">
              <button 
                v-if="bboxes.length > 0 && activeFile.status !== 'completed'"
                @click="bboxes = []"
                class="px-3 py-2 bg-slate-800/80 hover:bg-red-500/20 text-slate-400 hover:text-red-400 border border-slate-600/50 hover:border-red-500/50 rounded-lg transition-all flex items-center gap-2 text-sm font-medium"
                title="Clear all masks"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                Clear All
              </button>

              <button 
                v-if="activeFile.status === 'completed'"
                @click="reeditMask(selectedIndex)"
                class="px-4 py-2 bg-slate-700/50 border border-slate-600/50 text-slate-300 hover:text-white hover:bg-cyan-500/20 hover:border-cyan-400 rounded-lg transition-all flex items-center gap-2 text-sm font-medium"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                Adjust Mask
              </button>
              
              <button 
                v-if="bboxes.length > 0 && !processing && activeFile.status !== 'completed'"
                @click="triggerPreview(activeFile)"
                class="px-4 py-2 bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-400 hover:text-slate-900 rounded-lg transition-all flex items-center gap-2 text-sm font-medium shadow-[0_0_15px_rgba(34,211,238,0.1)] hover:shadow-[0_0_20px_rgba(34,211,238,0.4)]"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                Quick Preview
              </button>
            </div>
          </div>

          <!-- Canvas / Slider Area -->
          <div class="relative w-full flex-1 min-h-0 bg-slate-900/50 rounded-xl overflow-hidden border border-slate-700/50">
            <div v-if="activeFile.status === 'completed' && activeFile.resultPath" class="relative w-full h-full">
              <ImageSlider 
                :before-image="activeFile.path"
                :after-image="activeFile.resultPath"
              />
            </div>
            <div v-else class="relative w-full h-full">
              <MainCanvas 
                :image-path="activeFile.path"
                :initialBboxes="bboxes"
                @bboxesUpdate="(b) => bboxes = b"
              />
            </div>
          </div>
        </template>
        <div 
          v-else 
          class="w-full h-full flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-600 bg-slate-800/60 backdrop-blur-xl rounded-2xl transition-all hover:border-cyan-400 hover:bg-cyan-400/5"
          @dragover.prevent
          @drop.prevent="(e) => e.dataTransfer?.files && handleDrop(e.dataTransfer.files)"
        >
          <ImageIcon class="w-16 h-16 text-slate-500 mb-6 drop-shadow-lg" />
          <p class="text-2xl font-semibold text-slate-300 tracking-wide mb-2">Drag & Drop Images Here</p>
          <p class="text-sm text-slate-500">Unleash the magic to remove watermarks instantly</p>
        </div>
      </div>
    </div>
  </div>
</template>