<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps<{ imagePath: string }>()
const emit = defineEmits<{ (e: 'bboxesUpdate', bboxes: { x: number, y: number, w: number, h: number }[]): void }>()

const imgRef = ref<HTMLImageElement | null>(null)
const isDrawing = ref(false)
const startX = ref(0)
const startY = ref(0)
const currentX = ref(0)
const currentY = ref(0)
const boxes = ref<{ x: number, y: number, w: number, h: number }[]>([])

const imgState = ref({ width: 0, height: 0, natWidth: 0, natHeight: 0, xOffset: 0, yOffset: 0 })

const updateImgState = () => {
  if (!imgRef.value) return
  const img = imgRef.value
  const rect = img.getBoundingClientRect()
  
  const imgAspect = img.naturalWidth / img.naturalHeight
  const boxAspect = rect.width / rect.height
  
  let drawW = rect.width
  let drawH = rect.height
  let offsetX = 0
  let offsetY = 0
  
  if (imgAspect > boxAspect) {
    drawH = rect.width / imgAspect
    offsetY = (rect.height - drawH) / 2
  } else {
    drawW = rect.height * imgAspect
    offsetX = (rect.width - drawW) / 2
  }
  
  imgState.value = {
    width: drawW,
    height: drawH,
    natWidth: img.naturalWidth,
    natHeight: img.naturalHeight,
    xOffset: offsetX,
    yOffset: offsetY
  }
}

const handleMouseDown = (e: MouseEvent) => {
  if (!imgRef.value) return
  const rect = imgRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left - imgState.value.xOffset
  const y = e.clientY - rect.top - imgState.value.yOffset
  
  if (x < 0 || x > imgState.value.width || y < 0 || y > imgState.value.height) return
  
  isDrawing.value = true
  startX.value = x
  startY.value = y
  currentX.value = x
  currentY.value = y
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isDrawing.value || !imgRef.value) return
  const rect = imgRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left - imgState.value.xOffset
  const y = e.clientY - rect.top - imgState.value.yOffset
  currentX.value = Math.max(0, Math.min(x, imgState.value.width))
  currentY.value = Math.max(0, Math.min(y, imgState.value.height))
}

const handleMouseUp = () => {
  if (!isDrawing.value) return
  isDrawing.value = false
  
  const x = Math.min(startX.value, currentX.value)
  const y = Math.min(startY.value, currentY.value)
  const w = Math.abs(currentX.value - startX.value)
  const h = Math.abs(currentY.value - startY.value)
  
  if (w > 5 && h > 5) {
    boxes.value.push({
      x: x / imgState.value.width,
      y: y / imgState.value.height,
      w: w / imgState.value.width,
      h: h / imgState.value.height
    })
    emit('bboxesUpdate', boxes.value)
  }
}

const removeBox = (index: number) => {
  boxes.value.splice(index, 1)
  emit('bboxesUpdate', boxes.value)
}

const clearAll = () => {
  boxes.value = []
  emit('bboxesUpdate', boxes.value)
}

onMounted(() => {
  window.addEventListener('resize', updateImgState)
  setTimeout(updateImgState, 100)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateImgState)
})
</script>

<template>
  <div class="relative w-full h-full flex items-center justify-center bg-slate-900/50 rounded-xl overflow-hidden p-4">
    <div class="relative max-w-full max-h-full inline-flex">
      <img
        ref="imgRef"
        :src="`file://${imagePath}`"
        class="max-w-full max-h-full object-contain pointer-events-none"
        @load="updateImgState"
      />
      <!-- Confirmed Boxes -->
      <div
        v-for="(box, i) in boxes"
        :key="i"
        class="absolute border-2 border-cyan-400 bg-cyan-400/20 pointer-events-auto"
        :style="{
          left: `${imgState.xOffset + box.x * imgState.width}px`,
          top: `${imgState.yOffset + box.y * imgState.height}px`,
          width: `${box.w * imgState.width}px`,
          height: `${box.h * imgState.height}px`
        }"
      >
        <button 
          @click.stop="removeBox(i)" 
          class="absolute -top-3 -right-3 w-6 h-6 bg-slate-800 border border-slate-600 rounded-full flex items-center justify-center text-slate-300 hover:text-white hover:bg-red-500 hover:border-red-500 transition-colors shadow-lg cursor-pointer z-10"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
        </button>
      </div>

      <!-- Drawing Area Overlay (Mouse events) -->
      <div 
        class="absolute inset-0 cursor-crosshair z-0"
        @mousedown.stop="handleMouseDown"
        @mousemove.stop="handleMouseMove"
        @mouseup.stop="handleMouseUp"
        @mouseleave.stop="handleMouseUp"
      ></div>

      <!-- Currently Drawn Box (Preview) -->
      <div
        v-if="isDrawing && (startX !== currentX || startY !== currentY)"
        class="absolute border-2 border-blue-400 bg-blue-400/20 pointer-events-none z-10"
        :style="{
          left: `${imgState.xOffset + Math.min(startX, currentX)}px`,
          top: `${imgState.yOffset + Math.min(startY, currentY)}px`,
          width: `${Math.abs(currentX - startX)}px`,
          height: `${Math.abs(currentY - startY)}px`
        }"
      ></div>
    </div>
    
    <!-- Clear All Button -->
    <button 
      v-if="boxes.length > 0"
      @click.stop="clearAll"
      class="absolute top-4 right-4 px-3 py-1.5 bg-slate-800/80 hover:bg-red-500/90 text-slate-300 hover:text-white text-xs font-medium rounded-lg border border-slate-600/50 hover:border-red-500 transition-all shadow-lg backdrop-blur flex items-center gap-1"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
      Clear All
    </button>
  </div>
</template>