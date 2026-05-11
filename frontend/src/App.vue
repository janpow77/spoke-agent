<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import Toasts from './components/shared/Toasts.vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()

onMounted(() => {
  auth.hydrate()
})
</script>

<template>
  <RouterView />
  <Toasts />
</template>
