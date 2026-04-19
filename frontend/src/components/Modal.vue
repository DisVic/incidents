<script setup>
/**
 * Глобальное модальное окно (alert/confirm/prompt).
 * 
 * Работает в паре с composable useModal.
 * Поддерживает:
 * - Alert: только кнопка OK
 * - Confirm: кнопки Отмена/Подтвердить
 * - Prompt: input для ввода текста + кнопки
 * 
 * Закрытие по Esc или клику на backdrop.
 */
import { useModal } from '@/composables/useModal'

const { modalState, close, cancel } = useModal()

/**
 * Обработка подтверждения (Enter или кнопка).
 */
const handleConfirm = () => {
  if (modalState.value.type === 'prompt') {
    close(modalState.value.inputValue)
  } else {
    close(true)
  }
}

/**
 * Обработка клавиш (Esc/Enter).
 * @param {KeyboardEvent} e
 */
const handleKeydown = (e) => {
  if (e.key === 'Escape') {
    cancel()
  } else if (e.key === 'Enter' && modalState.value.type !== 'prompt') {
    handleConfirm()
  }
}
</script>

<template>
  <!-- Teleport рендерит модалку вне #app (в body) -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="modalState.isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @keydown="handleKeydown"
      >
        <!-- Затемнение фона (клик = отмена) -->
        <div
          class="absolute inset-0 bg-black/50 backdrop-blur-sm"
          @click="cancel"
        ></div>
        
        <!-- Модальное окно -->
        <div
          class="relative bg-white rounded-xl shadow-2xl w-full max-w-md transform transition-all"
          role="dialog"
          aria-modal="true"
        >
          <!-- Заголовок -->
          <div class="px-6 pt-6 pb-2">
            <h3 class="text-lg font-semibold text-slate-800">
              {{ modalState.title }}
            </h3>
          </div>
          
          <!-- Тело: сообщение + input для prompt -->
          <div class="px-6 py-4">
            <p v-if="modalState.message" class="text-slate-600 mb-4">
              {{ modalState.message }}
            </p>
            
            <!-- Input для prompt -->
            <input
              v-if="modalState.type === 'prompt'"
              v-model="modalState.inputValue"
              :type="modalState.inputType"
              :placeholder="modalState.inputPlaceholder"
              class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
              autofocus
              @keydown.enter="handleConfirm"
              @keydown.escape="cancel"
            />
          </div>
          
          <!-- Кнопки: Отмена + Подтвердить -->
          <div class="px-6 py-4 bg-slate-50 rounded-b-xl flex gap-3 justify-end">
            <button
              v-if="modalState.type !== 'alert'"
              @click="cancel"
              class="px-5 py-2.5 text-slate-700 bg-white border border-slate-300 rounded-lg font-medium hover:bg-slate-100 transition-colors"
            >
              Отмена
            </button>
            <button
              @click="handleConfirm"
              class="px-5 py-2.5 text-white bg-primary-600 rounded-lg font-medium hover:bg-primary-700 transition-colors"
            >
              {{ modalState.type === 'confirm' ? 'Подтвердить' : modalState.type === 'prompt' ? 'Продолжить' : 'OK' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-active .relative,
.fade-leave-active .relative {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.fade-enter-from .relative {
  transform: scale(0.95) translateY(-10px);
  opacity: 0;
}

.fade-leave-to .relative {
  transform: scale(0.95) translateY(-10px);
  opacity: 0;
}
</style>
