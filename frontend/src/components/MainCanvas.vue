<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps<{ imagePath: string }>()
const emit = defineEmits<{ (e: 'bboxUpdate', bbox: { x: number, y: number, w: number, h: number } | null): void }>()

const imgRef = ref<HTMLImageElement | null>(null)
const isDrawing = ref(false)
const startX = ref(0)
const startY = ref(0)
const currentX = ref(0)
const currentY = ref(0)

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
  emit('bboxUpdate', null)
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
    emit('bboxUpdate', {
      x: x / imgState.value.width,
      y: y / imgState.value.height,
      w: w / imgState.value.width,
      h: h / imgState.value.height
    })
  }
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
      <!-- Drawing Area Overlay -->
      <div 
        class="absolute inset-0 cursor-crosshair"
        @mousedown.stop="handleMouseDown"
        @mousemove.stop="handleMouseMove"
        @mouseup.stop="handleMouseUp"
        @mouseleave.stop="handleMouseUp"
      >
        <!-- Drawn Box -->
        <div
          v-if="startX !== currentX || startY !== currentY"
          class="absolute border-2 border-blue-400 bg-blue-400/20 pointer-events-none"
          :style="{
            left: `${imgState.xOffset + Math.min(startX, currentX)}px`,
            top: `${imgState.yOffset + Math.min(startY, currentY)}px`,
            width: `${Math.abs(currentX - startX)}px`,
            height: `${Math.abs(currentY - startY)}px`
          }"
        ></div>
      </div>
    </div>
  </div>
</template>