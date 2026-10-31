package com.segundatela.app

import android.content.SharedPreferences

/** Preferências do usuário (salvas entre usos). */
data class Ajustes(
    var modo: String = "estender",      // estender | espelhar
    var lado: String = "direita",       // direita | esquerda | acima
    var resolucao: Int = 100,           // % da resolução nativa do tablet
    var escala: Int = 0,                // escala do Windows em %, 0 = automática
    var fps: Int = 60,
    var mbps: Int = 0,                  // 0 = automático
    var toque: String = "nativo",       // nativo | mouse | desligado
    var caneta: Boolean = true,         // S Pen com pressão e inclinação
    var palma: Boolean = false,         // só a caneta age; dedos ignorados
    var barra: Boolean = true,          // barra lateral de atalhos
    var orientacao: String = "auto",    // auto | horizontal | vertical
    var compat: Boolean = false,        // MJPEG em vez de H.264
    var porta: Int = 8080,
    var pin: String = "",
    var autoconectar: Boolean = false,
    var ultimoHost: String = ""
) {
    fun salvar(p: SharedPreferences) {
        p.edit()
            .putString("modo", modo).putString("lado", lado)
            .putInt("resolucao", resolucao).putInt("escala", escala)
            .putInt("fps3", fps).putInt("mbps", mbps)
            .putString("toque", toque).putBoolean("caneta", caneta)
            .putBoolean("palma", palma).putBoolean("barra", barra)
            .putString("orientacao", orientacao).putBoolean("compat", compat)
            .putInt("porta3", porta).putString("pin", pin)
            .putBoolean("autoconectar", autoconectar)
            .putString("host", ultimoHost)
            .apply()
    }

    companion object {
        fun carregar(p: SharedPreferences) = Ajustes(
            modo = p.getString("modo", "estender")!!,
            lado = p.getString("lado", "direita")!!,
            resolucao = p.getInt("resolucao", 100),
            escala = p.getInt("escala", 0),
            fps = p.getInt("fps3", 60),
            mbps = p.getInt("mbps", 0),
            toque = p.getString("toque", "nativo")!!,
            caneta = p.getBoolean("caneta", true),
            palma = p.getBoolean("palma", false),
            barra = p.getBoolean("barra", true),
            orientacao = p.getString("orientacao", "auto")!!,
            compat = p.getBoolean("compat", false),
            porta = p.getInt("porta3", 8080),
            pin = p.getString("pin", "")!!,
            autoconectar = p.getBoolean("autoconectar", false),
            ultimoHost = p.getString("host", "")!!
        )

        val ESCALAS = listOf(100, 125, 150, 175, 200, 225, 250, 300)

        /** Escala do Windows que deixa a interface num tamanho confortável. */
        fun escalaAuto(larguraMaior: Int): Int {
            val alvo = larguraMaior * 100 / 1440
            return ESCALAS.minByOrNull { kotlin.math.abs(it - alvo) } ?: 100
        }
    }
}
