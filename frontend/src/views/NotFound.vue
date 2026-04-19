<script setup>
/**
 * Страница 404: отображается при переходе по несуществующему маршруту.
 */
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <!-- Код ошибки -->
      <h1 class="text-6xl font-bold text-slate-300 mb-4">404</h1>
      <p class="text-xl text-slate-600 mb-6">Страница не найдена</p>
      <!-- Ссылка на главную -->
      <router-link to="/" class="px-6 py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700">
        На главную
      </router-link>
    </div>
  </div>
</template>
