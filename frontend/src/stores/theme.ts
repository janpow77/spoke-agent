import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const stored = localStorage.getItem('spoke_theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const theme = ref<'light' | 'dark'>(stored === 'light' ? 'light' : (stored === 'dark' || prefersDark) ? 'dark' : 'light')

  watch(theme, (v) => {
    localStorage.setItem('spoke_theme', v)
    document.documentElement.classList.toggle('dark', v === 'dark')
  }, { immediate: true })

  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return { theme, toggle }
})
