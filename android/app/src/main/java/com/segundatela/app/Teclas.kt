package com.segundatela.app

import android.view.KeyEvent

/** Teclado físico do tablet (ex.: Book Cover Keyboard) -> código virtual do Windows. */
object Teclas {
    private val mapa: Map<Int, Int> = HashMap<Int, Int>().apply {
        for (i in 0..25) put(KeyEvent.KEYCODE_A + i, 0x41 + i)
        for (i in 0..9) put(KeyEvent.KEYCODE_0 + i, 0x30 + i)
        for (i in 0..11) put(KeyEvent.KEYCODE_F1 + i, 0x70 + i)
        for (i in 0..9) put(KeyEvent.KEYCODE_NUMPAD_0 + i, 0x60 + i)
        put(KeyEvent.KEYCODE_ENTER, 0x0D); put(KeyEvent.KEYCODE_NUMPAD_ENTER, 0x0D)
        put(KeyEvent.KEYCODE_ESCAPE, 0x1B); put(KeyEvent.KEYCODE_TAB, 0x09)
        put(KeyEvent.KEYCODE_SPACE, 0x20); put(KeyEvent.KEYCODE_DEL, 0x08)
        put(KeyEvent.KEYCODE_FORWARD_DEL, 0x2E); put(KeyEvent.KEYCODE_INSERT, 0x2D)
        put(KeyEvent.KEYCODE_MOVE_HOME, 0x24); put(KeyEvent.KEYCODE_MOVE_END, 0x23)
        put(KeyEvent.KEYCODE_PAGE_UP, 0x21); put(KeyEvent.KEYCODE_PAGE_DOWN, 0x22)
        put(KeyEvent.KEYCODE_DPAD_LEFT, 0x25); put(KeyEvent.KEYCODE_DPAD_UP, 0x26)
        put(KeyEvent.KEYCODE_DPAD_RIGHT, 0x27); put(KeyEvent.KEYCODE_DPAD_DOWN, 0x28)
        put(KeyEvent.KEYCODE_SHIFT_LEFT, 0xA0); put(KeyEvent.KEYCODE_SHIFT_RIGHT, 0xA1)
        put(KeyEvent.KEYCODE_CTRL_LEFT, 0xA2); put(KeyEvent.KEYCODE_CTRL_RIGHT, 0xA3)
        put(KeyEvent.KEYCODE_ALT_LEFT, 0xA4); put(KeyEvent.KEYCODE_ALT_RIGHT, 0xA5)
        put(KeyEvent.KEYCODE_META_LEFT, 0x5B); put(KeyEvent.KEYCODE_META_RIGHT, 0x5C)
        put(KeyEvent.KEYCODE_CAPS_LOCK, 0x14); put(KeyEvent.KEYCODE_NUM_LOCK, 0x90)
        put(KeyEvent.KEYCODE_SYSRQ, 0x2C); put(KeyEvent.KEYCODE_MENU, 0x5D)
        put(KeyEvent.KEYCODE_MINUS, 0xBD); put(KeyEvent.KEYCODE_EQUALS, 0xBB)
        put(KeyEvent.KEYCODE_LEFT_BRACKET, 0xDB); put(KeyEvent.KEYCODE_RIGHT_BRACKET, 0xDD)
        put(KeyEvent.KEYCODE_BACKSLASH, 0xDC); put(KeyEvent.KEYCODE_SEMICOLON, 0xBA)
        put(KeyEvent.KEYCODE_APOSTROPHE, 0xDE); put(KeyEvent.KEYCODE_GRAVE, 0xC0)
        put(KeyEvent.KEYCODE_COMMA, 0xBC); put(KeyEvent.KEYCODE_PERIOD, 0xBE)
        put(KeyEvent.KEYCODE_SLASH, 0xBF)
        put(KeyEvent.KEYCODE_NUMPAD_ADD, 0x6B); put(KeyEvent.KEYCODE_NUMPAD_SUBTRACT, 0x6D)
        put(KeyEvent.KEYCODE_NUMPAD_MULTIPLY, 0x6A); put(KeyEvent.KEYCODE_NUMPAD_DIVIDE, 0x6F)
        put(KeyEvent.KEYCODE_NUMPAD_DOT, 0x6E)
        put(KeyEvent.KEYCODE_VOLUME_MUTE, 0xAD)
        put(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, 0xB3)
        put(KeyEvent.KEYCODE_MEDIA_NEXT, 0xB0); put(KeyEvent.KEYCODE_MEDIA_PREVIOUS, 0xB1)
        // Teclas ABNT2 do teclado brasileiro
        put(KeyEvent.KEYCODE_RO, 0xC1)
    }

    fun vk(keyCode: Int): Int? = mapa[keyCode]

    /** Evento veio de um teclado de verdade (não da tela nem dos botões do tablet)? */
    fun fisico(e: KeyEvent): Boolean {
        val dev = e.device ?: return false
        return !dev.isVirtual && dev.keyboardType == android.view.InputDevice.KEYBOARD_TYPE_ALPHABETIC
    }
}
