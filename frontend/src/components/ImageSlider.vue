<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  beforeImage: string
  afterImage: string
}>()

const sliderPosition = ref(50)
</script>

<template>
  <div class="relative w-full h-full flex items-center justify-center overflow-hidden rounded-lg shadow-2xl user-select-none bg-slate-900/50">
    <!-- Base (After Image) -->
    <img 
      :src="`file://${afterImage}`" 
      class="w-full h-full object-contain block" 
      draggable="false"
    />
    
    <!-- Overlay (Before Image) clipped -->
    <div class="absolute inset-0 flex justify-center items-center pointer-events-none">
       <img 
        :src="`file://${beforeImage}`" 
        class="w-full h-full object-contain pointer-events-none" 
        :style="{ clipPath: `inset(0 ${100 - sliderPosition}% 0 0)` }"
        draggable="false"
      />
    </div>

    <!-- Slider Input -->
    <input 
      type="range" 
      min="0" 
      max="100" 
      v-model="sliderPosition" 
      class="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-10"
    />
    
    <!-- Slider Line visual -->
    <div 
      class="absolute top-0 bottom-0 w-1 bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)] pointer-events-none z-0 flex items-center justify-center"
      :style="{ left: `calc(${sliderPosition}% - 2px)` }"
    >
      <div class="w-8 h-8 rounded-full bg-cyan-400 border-2 border-slate-900 shadow-lg flex items-center justify-center">
        <svg class="w-4 h-4 text-slate-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l4-4 4 4m0 6l-4 4-4-4"></path>
        </svg>
      </div>
    </div>

    <div class="absolute top-4 left-4 bg-slate-900/60 backdrop-blur text-xs px-2 py-1 rounded text-slate-200 pointer-events-none">Before</div>
    <div class="absolute top-4 right-4 bg-slate-900/60 backdrop-blur text-xs px-2 py-1 rounded text-cyan-400 pointer-events-none">After</div>
  </div>
</template>
