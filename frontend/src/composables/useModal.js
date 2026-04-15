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

  const close = (result) => {
    if (modalState.value.resolvePromise) {
      modalState.value.resolvePromise(result)
    }
    modalState.value.isOpen = false
  }

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
