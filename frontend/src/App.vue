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

const triggerProcess = async () => {
  if (files.value.length === 0 || bboxes.value.length === 0) {
    alert("Please drop files and draw at least one box over the watermark.")
    return
  }
  const filesToProcess = files.value.filter(f => f.status !== 'completed')
  if (filesToProcess.length === 0) {
    alert("All files have already been processed.")
    return
  }

  processing.value = true
  engineState.value = 'idle' // Will be updated by WS
  filesToProcess.forEach(f => {
    f.status = 'queued'
    f.progress = 0
  })
  
  try {
    const res = await fetch("http://127.0.0.1:8000/api/v1/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        job_id: "job-" + Date.now(),
        input_files: filesToProcess.map(f => f.path),
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
          f.resultPath = msg.result_path + "?t=" + Date.now()
        }
      } else if (msg.status === 'completed') {
        processing.value = false
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
          }
        })
        ws.close()
      }
    }
  } catch (e) {
    alert("Failed to start processing: " + e)
    processing.value = false
  }
}

const cancelProcess = async () => {
  if (!currentJobId.value || !processing.value) return
  
  // Optimistically update UI
  processing.value = false
  engineState.value = 'idle'
  files.value.forEach(f => {
    if (f.status === 'queued' || f.status === 'processing') {
      f.status = 'cancelled'
    }
  })
  
  try {
    await fetch(`http://127.0.0.1:8000/api/v1/jobs/${currentJobId.value}/cancel`, {
      method: "POST"
    })
  } catch (e) {
    console.error("Failed to cancel job", e)
  }
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

      <div class="flex-1 rounded-2xl bg-slate-800/60 backdrop-blur-xl border border-slate-600/30 p-6 min-w-0 min-h-0">
        <template v-if="activeFile">
          <ImageSlider 
            v-if="activeFile.status === 'completed' && activeFile.resultPath"
            :before-image="activeFile.path"
            :after-image="activeFile.resultPath"
          />
          <MainCanvas 
            v-else
            :image-path="activeFile.path"
            :initialBboxes="bboxes"
            @bboxesUpdate="(b) => bboxes = b"
          />
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