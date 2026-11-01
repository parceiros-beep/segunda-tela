package com.segundatela.app

/** Botões possíveis da barra lateral; o usuário escolhe quais aparecem. */
object Atalhos {
    /** tipo: "combo" (atalho), "mod" (tecla que fica pressionada), "teclado", "direito". */
    data class Item(
        val id: String, val texto: String, val nome: String,
        val tipo: String, val valor: String = "", val grupo: Int = 0
    )

    val todos = listOf(
        Item("teclado", "⌨", "Teclado", "teclado", grupo = 0),
        Item("ctrl", "Ctrl", "Ctrl (fica pressionado)", "mod", "162", 0),
        Item("shift", "Shift", "Shift (fica pressionado)", "mod", "160", 0),
        Item("alt", "Alt", "Alt (fica pressionado)", "mod", "164", 0),
        Item("desfazer", "↶", "Desfazer", "combo", "CTRL+Z", 1),
        Item("refazer", "↷", "Refazer", "combo", "CTRL+Y", 1),
        Item("copiar", "Copiar", "Copiar", "combo", "CTRL+C", 1),
        Item("colar", "Colar", "Colar", "combo", "CTRL+V", 1),
        Item("recortar", "Recortar", "Recortar", "combo", "CTRL+X", 1),
        Item("salvar", "Salvar", "Salvar", "combo", "CTRL+S", 1),
        Item("tudo", "Tudo", "Selecionar tudo", "combo", "CTRL+A", 1),
        Item("esc", "Esc", "Esc", "combo", "ESC", 2),
        Item("del", "Del", "Delete", "combo", "DELETE", 2),
        Item("enter", "⏎", "Enter", "combo", "ENTER", 2),
        Item("iniciar", "⊞", "Menu Iniciar", "combo", "WIN", 2),
        Item("alttab", "Alt⇥", "Alternar janelas (Alt+Tab)", "combo", "ALT+TAB", 2),
        Item("area", "Área", "Mostrar área de trabalho", "combo", "WIN+D", 2),
        Item("zoommais", "Zoom+", "Aumentar zoom", "combo", "CTRL+PLUS", 2),
        Item("zoommenos", "Zoom−", "Diminuir zoom", "combo", "CTRL+MINUS", 2),
        Item("direito", "Dir.", "Próximo toque = botão direito", "direito", grupo = 3)
    )

    /** Vazio = todos; "-" = nenhum. */
    fun escolhidos(aj: Ajustes): List<Item> = escolhidos(aj.barraItens)

    fun escolhidos(lista: String): List<Item> {
        if (lista.isBlank()) return todos
        val ids = lista.split(",").toSet()
        return todos.filter { it.id in ids }
    }
}
