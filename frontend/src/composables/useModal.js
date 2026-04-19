/**
 * Composable для модальных окон (alert/confirm/prompt).
 * 
 * Используется вместо стандартных window.alert/confirm.
 * Работает через реактивное состояние modalState, которое
 * читается компонентом Modal.vue.
 * 
 * @example
 * const { alert, confirm } = useModal()
 * await alert('Ошибка!')
 * if (await confirm('Удалить?')) { ... }
 */
import { ref } from 'vue'

const modalState = ref({
  isOpen: false,
  type: 'alert', // 'alert' | 'confirm' | 'prompt'
  title: '',
  message: '',
  inputValue: '',
  inputPlaceholder: '',
  inputType: 'text',
  resolvePromise: null,
})

export function useModal() {
  /**
   * Показать alert-сообщение.
   * @param {string} message - Текст сообщения
   * @param {string} title - Заголовок окна
   * @returns {Promise<void>}
   */
  const alert = (message, title = 'Внимание') => {
    return new Promise((resolve) => {
      modalState.value = {
        isOpen: true,
        type: 'alert',
        title,
        message,
        inputValue: '',
        inputPlaceholder: '',
        inputType: 'text',
        resolvePromise: resolve,
      }
    })
  }

  /**
   * Показать confirm-диалог.
   * @param {string} message - Текст сообщения
   * @param {string} title - Заголовок окна
   * @returns {Promise<boolean>}
   */
  const confirm = (message, title = 'Подтверждение') => {
    return new Promise((resolve) => {
      modalState.value = {
        isOpen: true,
        type: 'confirm',
        title,
        message,
        inputValue: '',
        inputPlaceholder: '',
        inputType: 'text',
        resolvePromise: resolve,
      }
    })
  }

  /**
   * Показать prompt-диалог для ввода текста.
   * @param {string} message - Текст сообщения
   * @param {string} defaultValue - Значение по умолчанию
   * @param {string} title - Заголовок окна
   * @param {string} inputType - Тип input (text, number, email, etc.)
   * @param {string} placeholder - Подсказка для input
   * @returns {Promise<string|null>}
   */
  const prompt = (message, defaultValue = '', title = 'Ввод данных', inputType = 'text', placeholder = '') => {
    return new Promise((resolve) => {
      modalState.value = {
        isOpen: true,
        type: 'prompt',
        title,
        message,
        inputValue: defaultValue,
        inputPlaceholder: placeholder,
        inputType,
        resolvePromise: resolve,
      }
    })
  }

  /**
   * Закрыть модальное окно с результатом.
   * @param {*} result - Результат для разрешения промиса
   */
  const close = (result) => {
    if (modalState.value.resolvePromise) {
      modalState.value.resolvePromise(result)
    }
    modalState.value.isOpen = false
  }

  /**
   * Отмена модального окна.
   * Возвращает false для confirm/alert, null для prompt.
   */
  const cancel = () => {
    if (modalState.value.resolvePromise) {
      if (modalState.value.type === 'prompt') {
        modalState.value.resolvePromise(null)
      } else if (modalState.value.type === 'confirm') {
        modalState.value.resolvePromise(false)
      } else {
        modalState.value.resolvePromise(false)
      }
    }
    modalState.value.isOpen = false
  }

  return {
    modalState,
    alert,
    confirm,
    prompt,
    close,
    cancel,
  }
}
