import { ref } from 'vue'

// Глобальное состояние модального окна
const modalState = ref({
  isOpen: false,
  type: 'alert', // 'alert' | 'confirm' | 'prompt'
  title: '',
  message: '',
  inputValue: '',
  inputPlaceholder: '',
  inputType: 'text',
  resolvePromise: null, // Функция для возврата результата
})

// Композабл для управления модальными окнами
export function useModal() {
  // Показать alert — окно с сообщением и кнопкой OK
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

  // Показать confirm — окно с подтверждением (OK/Отмена)
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

  // Показать prompt — окно для ввода данных пользователем
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

  // Закрыть модалку с результатом — вызываем resolvePromise
  const close = (result) => {
    if (modalState.value.resolvePromise) {
      modalState.value.resolvePromise(result)
    }
    modalState.value.isOpen = false
  }

  // Отмена действия — возвращаем null/false в зависимости от типа
  const cancel = () => {
    if (modalState.value.resolvePromise) {
      if (modalState.value.type === 'prompt') {
        modalState.value.resolvePromise(null) // Для prompt возвращаем null
      } else if (modalState.value.type === 'confirm') {
        modalState.value.resolvePromise(false) // Для confirm возвращаем false
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
