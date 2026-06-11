<script setup lang="ts">
import { ref, computed } from 'vue'
import Sidebar from './components/Sidebar.vue'
import MainCanvas from './components/MainCanvas.vue'
import ImageSlider from './components/ImageSlider.vue'

const files = ref<{ path: string, status: string, progress: number, resultPath?: string }[]>([])
const processing = ref(false)
const selectedIndex = ref<number | null>(null)
const bbox = ref<{ x: number, y: number, w: number, h: number } | null>(null)
const outputDir = ref(localStorage.getItem('delogo_output_dir') || '/tmp/delogo_out')

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
  if (files.value.length === 0 || !bbox.value) {
    alert("Please drop files and draw a box over the watermark.")
    return
  }
  processing.value = true
  files.value.forEach(f => {
    f.status = 'queued'
    f.progress = 0
    f.resultPath = undefined
  })
  
  try {
    const res = await fetch("http://127.0.0.1:8000/api/v1/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        job_id: "job-" + Date.now(),
        input_files: files.value.map(f => f.path),
        output_dir: outputDir.value,
        bbox: bbox.value
      })
    })
    const data = await res.json()
    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/progress/${data.job_id}`)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.status === 'processing' && msg.progress) {
        const f = files.value.find(x => x.path.endsWith(msg.current_file))
        if (f) f.progress = msg.progress
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
        alert(msg.message)
      }
    }
  } catch (e) {
    alert("Failed to start processing: " + e)
    processing.value = false
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
        :output-dir="outputDir"
        @drop="handleDrop"
        @start="triggerProcess"
        @select="(idx) => selectedIndex = idx"
        @update:output-dir="updateOutputDir"
        @remove="removeFile"
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
            @bboxUpdate="(b) => bbox = b"
          />
        </template>
        <div v-else class="w-full h-full flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-700/50 rounded-xl">
          <div class="text-6xl mb-4">🖼️</div>
          <p class="text-lg">Select an image to preview</p>
        </div>
      </div>
    </div>
  </div>
</template>