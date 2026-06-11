<script setup lang="ts">
import { computed } from 'vue'
import { Play, Loader2, Trash2, CheckCircle, Clock, FolderOpen, ImageIcon, Settings2 } from 'lucide-vue-next'

const props = defineProps<{
  files: { path: string, status: string, progress: number, resultPath?: string }[]
  processing: boolean
  engineState: 'idle' | 'warming' | 'processing'
  outputDir: string
}>()

const emit = defineEmits<{
  (e: 'drop', files: FileList | File[]): void
  (e: 'start'): void
  (e: 'select', index: number): void
  (e: 'update:outputDir', dir: string): void
  (e: 'remove', index: number): void
  (e: 'cancel'): void
  (e: 'clearAll'): void
}>()

const globalProgress = computed(() => {
  if (props.files.length === 0) return 0
  const completed = props.files.filter(f => f.status === 'completed' || f.status === 'error' || f.status === 'cancelled').length
  return Math.round((completed / props.files.length) * 100)
})

const completedCount = computed(() => props.files.filter(f => f.status === 'completed').length)

const isElectron = !!(window as any).process?.versions?.electron

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  if (e.dataTransfer?.files) {
    emit('drop', e.dataTransfer.files)
  }
}

const handleFileSelect = async () => {
  if (!isElectron) return
  const { ipcRenderer } = (window as any).require('electron')
  try {
    const filePaths = await ipcRenderer.invoke('dialog:openFile')
    if (filePaths && filePaths.length > 0) {
      const fs = (window as any).require('fs')
      const path = (window as any).require('path')
      
      let allImagePaths: string[] = []
      
      for (const p of filePaths) {
        const stat = fs.statSync(p)
        if (stat.isDirectory()) {
          const files = fs.readdirSync(p)
          const imageFiles = files
            .filter((f: string) => f.match(/\.(jpg|jpeg|png)$/i))
            .map((f: string) => path.join(p, f))
          allImagePaths = allImagePaths.concat(imageFiles)
        } else {
          if (p.match(/\.(jpg|jpeg|png)$/i)) {
            allImagePaths.push(p)
          }
        }
      }
      
      if (allImagePaths.length > 0) {
        const filesToAdd = allImagePaths.map((p: string) => ({ path: p }))
        emit('drop', filesToAdd as any)
      } else {
        alert("No images found in the selected locations.")
      }
    }
  } catch (err) {
    console.error(err)
  }
}

const handleChangeOutputDir = async () => {
  if (!isElectron) return
  const { ipcRenderer } = (window as any).require('electron')
  try {
    const dirPaths = await ipcRenderer.invoke('dialog:openDirectory')
    if (dirPaths && dirPaths.length > 0) {
      emit('update:outputDir', dirPaths[0])
    }
  } catch (err) {
    console.error(err)
  }
}
</script>

<template>
  <div class="w-1/3 flex flex-col gap-4">
    <!-- Dropzone -->
    <div 
      class="h-40 rounded-2xl border-2 border-dashed border-slate-600 bg-slate-800/60 backdrop-blur-xl flex flex-col items-center justify-center transition-all hover:border-cyan-400 hover:bg-cyan-400/5 relative"
      @dragover.prevent
      @drop="handleDrop"
    >
      <ImageIcon class="w-8 h-8 text-slate-500 mb-2" />
      <p class="text-base text-slate-300 font-medium mb-1">Drag Images or Folders Here</p>
      
      <div class="flex gap-3 mt-2 z-10">
        <button 
          @click="handleFileSelect" 
          class="flex items-center gap-1.5 px-4 py-2 bg-slate-700/50 hover:bg-slate-600 text-sm text-slate-300 rounded-lg transition-colors border border-slate-600/50"
        >
          <FolderOpen class="w-4 h-4" /> Select Files / Folder
        </button>
      </div>
    </div>
    
    <!-- Output Dir Settings -->
    <div class="rounded-xl border border-slate-700 bg-slate-800/40 p-3 flex flex-col gap-2">
      <div class="flex items-center justify-between text-slate-300 text-sm">
        <span class="flex items-center gap-1.5 font-medium"><Settings2 class="w-4 h-4 text-cyan-400"/> Output Directory</span>
        <button 
          @click="handleChangeOutputDir"
          class="text-xs px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded transition-colors text-slate-300"
        >Change</button>
      </div>
      <div class="text-xs text-slate-500 truncate bg-slate-900/50 px-2 py-1.5 rounded" :title="outputDir">
        {{ outputDir }}
      </div>
    </div>

    <!-- Action Button / Progress Area -->
    <div v-if="!processing" class="flex">
      <button 
        @click="emit('start')"
        :disabled="files.length === 0"
        class="w-full rounded-full px-6 py-4 font-medium text-white transition-all shadow-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-400 hover:to-purple-500 shadow-purple-500/20"
      >
        <Play class="w-5 h-5" fill="currentColor" />
        <span>Start Auto-Removal</span>
      </button>
    </div>
    
    <div v-else-if="engineState === 'idle' || engineState === 'warming'" class="flex">
      <div class="w-full rounded-full px-6 py-4 font-medium shadow-[0_0_20px_rgba(34,211,238,0.2)] flex items-center justify-center gap-3 bg-slate-800/80 border border-cyan-500/40 relative overflow-hidden">
        <div class="absolute inset-0 bg-cyan-400/5 animate-pulse"></div>
        <Loader2 class="w-5 h-5 animate-spin text-cyan-400 relative z-10" />
        <span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400 font-bold relative z-10 tracking-wide">Warming up AI Engine... ⚡️</span>
      </div>
    </div>

    <div v-else class="flex flex-col gap-3 p-4 rounded-xl border border-slate-700 bg-slate-800/80 shadow-[0_0_30px_rgba(168,85,247,0.15)] relative overflow-hidden">
      <div class="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-cyan-400 to-purple-500"></div>
      <div class="flex justify-between items-end relative z-10">
        <div class="flex flex-col gap-1">
          <span class="text-xs text-slate-400 font-medium tracking-wide uppercase">Batch Progress</span>
          <span class="text-xl font-bold text-slate-100">{{ completedCount }} <span class="text-sm text-slate-500 font-normal">/ {{ files.length }}</span></span>
        </div>
        <span class="text-sm font-bold text-cyan-400">{{ globalProgress }}%</span>
      </div>
      <div class="h-2.5 w-full bg-slate-900/80 rounded-full overflow-hidden shadow-inner relative z-10 border border-slate-700/50">
        <div class="h-full bg-gradient-to-r from-cyan-400 to-purple-500 transition-all duration-300 relative" :style="{ width: `${globalProgress}%` }">
          <div class="absolute inset-0 bg-white/20 animate-pulse"></div>
        </div>
      </div>
      <button 
        @click="emit('cancel')"
        class="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 transition-all text-sm font-bold tracking-wide relative z-10 hover:shadow-[0_0_15px_rgba(239,68,68,0.2)]"
      >
        <div class="w-2.5 h-2.5 rounded-sm bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div> Stop Process
      </button>
    </div>

    <!-- Queue List Header -->
    <div class="flex justify-between items-center px-1">
      <span class="text-xs text-slate-400 font-medium tracking-wide uppercase">Queue List</span>
      <button 
        v-if="files.length > 0 && !processing"
        @click="emit('clearAll')"
        class="text-xs text-slate-500 hover:text-red-400 transition-colors flex items-center gap-1"
        title="Clear all files"
      >
        <Trash2 class="w-3.5 h-3.5" /> Clear All
      </button>
    </div>

    <!-- Queue List -->
    <TransitionGroup name="list" tag="div" class="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar pb-4 relative">
      <div 
        v-for="(file, idx) in files" 
        :key="file.path"
        @click="emit('select', idx)"
        class="h-16 px-4 rounded-xl border border-slate-700 bg-slate-800/40 hover:bg-slate-700/50 transition-colors flex items-center justify-between cursor-pointer relative overflow-hidden group"
      >
        <div class="flex items-center gap-3 truncate max-w-[70%]">
          <div class="w-10 h-10 rounded-lg bg-slate-900/50 flex-shrink-0 flex items-center justify-center overflow-hidden">
            <img :src="`file://${file.path}`" class="w-full h-full object-cover opacity-80" />
          </div>
          <div class="truncate">
            <p class="text-sm font-medium text-slate-200 truncate" :title="file.path">{{ file.path.split('/').pop() }}</p>
            <p class="text-xs text-slate-500">{{ file.status }}</p>
          </div>
        </div>
        
        <div class="flex items-center gap-2">
          <CheckCircle v-if="file.status === 'completed'" class="w-5 h-5 text-emerald-400" />
          <Clock v-else-if="file.status === 'processing'" class="w-5 h-5 text-cyan-400 animate-pulse" />
          <button 
            @click.stop="emit('remove', idx)"
            class="text-slate-500 hover:text-red-400 transition-colors p-1"
            title="Remove from queue"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>

        <!-- Progress Bar (Thin line at bottom) -->
        <div class="absolute bottom-0 left-0 h-1 bg-slate-700 w-full">
          <div 
            class="h-full bg-cyan-400 transition-all duration-300"
            :style="{ width: `${file.progress}%` }"
          ></div>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #475569;
}

/* TransitionGroup animations */
.list-move, /* apply transition to moving elements */
.list-enter-active,
.list-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.list-enter-from {
  opacity: 0;
  transform: translateY(15px);
}

.list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

/* ensure leaving items are taken out of layout flow so that moving
   animations can be calculated correctly. */
.list-leave-active {
  position: absolute;
}
</style>
