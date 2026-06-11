<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { Trash2 } from 'lucide-vue-next'

const props = defineProps<{ 
  imagePath: string
  initialBboxes?: { x: number, y: number, w: number, h: number }[]
}>()
const emit = defineEmits<{ (e: 'bboxesUpdate', bboxes: { x: number, y: number, w: number, h: number }[]): void }>()

const imgRef = ref<HTMLImageElement | null>(null)
const isDrawing = ref(false)
const startX = ref(0)
const startY = ref(0)
const currentX = ref(0)
const currentY = ref(0)
const boxes = ref<{ x: number, y: number, w: number, h: number }[]>([...(props.initialBboxes || [])])

watch(() => props.initialBboxes, (newVal) => {
  if (newVal) {
    boxes.value = [...newVal]
  }
}, { deep: true })

const imgState = ref({ width: 0, height: 0, natWidth: 0, natHeight: 0, xOffset: 0, yOffset: 0 })
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  window.addEventListener('resize', updateImgState)
  if (imgRef.value) {
    resizeObserver = new ResizeObserver(() => {
      updateImgState()
    })
    resizeObserver.observe(imgRef.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateImgState)
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})

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
      <!-- Bounding boxes -->
      <div 
        v-for="(box, idx) in boxes" 
        :key="idx"
        class="absolute border-2 border-cyan-400 bg-cyan-500/10 shadow-[0_0_15px_rgba(34,211,238,0.3)] transition-colors duration-200 group rounded-sm z-10"
        :style="{
          left: `${imgState.xOffset + box.x * imgState.width}px`,
          top: `${imgState.yOffset + box.y * imgState.height}px`,
          width: `${box.w * imgState.width}px`,
          height: `${box.h * imgState.height}px`
        }"
      >
        <div class="absolute inset-0 bg-gradient-to-b from-cyan-400/0 via-cyan-400/10 to-purple-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
        <button 
          @click.stop="removeBox(idx)"
          class="absolute -top-3 -right-3 bg-slate-800 border border-slate-600 text-slate-300 rounded-full p-1.5 opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-red-500 hover:text-white hover:border-red-500 shadow-lg hover:scale-110 z-20"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Current drawing box -->
      <div 
        v-if="isDrawing"
        class="absolute border border-cyan-400 border-dashed bg-cyan-400/10 pointer-events-none z-20 shadow-[0_0_10px_rgba(34,211,238,0.3)]"
        :style="{
          left: `${imgState.xOffset + Math.min(startX, currentX)}px`,
          top: `${imgState.yOffset + Math.min(startY, currentY)}px`,
          width: `${Math.abs(currentX - startX)}px`,
          height: `${Math.abs(currentY - startY)}px`
        }"
      ></div>

      <!-- Drawing Area Overlay (Mouse events) -->
      <div 
        class="absolute inset-0 cursor-crosshair z-0"
        @mousedown.stop="handleMouseDown"
        @mousemove.stop="handleMouseMove"
        @mouseup.stop="handleMouseUp"
        @mouseleave.stop="handleMouseUp"
      ></div>
    </div>
  </div>
</template>