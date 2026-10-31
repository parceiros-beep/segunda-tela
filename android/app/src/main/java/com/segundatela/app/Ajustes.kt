package com.segundatela.app

import android.content.SharedPreferences

/** Preferências do usuário (salvas entre usos). */
data class Ajustes(
    // Tela
    var modo: String = "estender",      // estender | espelhar
    var lado: String = "direita",       // direita | esquerda | acima
    var resolucao: Int = 100,           // % da resolução nativa do tablet (25..100)
    var escala: Int = 0,                // escala do Windows em %, 0 = automática
    var orientacao: String = "auto",    // auto | horizontal | vertical
    // Vídeo e desempenho
    var perfil: String = "personalizado", // desenho | trabalho | video | economia | personalizado
    var codec: String = "h264",         // h264 | h265
    var fps: Int = 60,                  // 0 = automático; senão livre, de 10 a 60
    var mbps: Int = 0,                  // 0 = automático; 2..150
    var taxa: String = "cbr",           // cbr | vbr | cq
    var cq: Int = 23,                   // qualidade constante (menor = melhor)
    var velocidade: String = "rapida",  // rapida | equilibrada | qualidade
    var gop: Float = 2f,                // segundos entre quadros-chave
    var intra: Boolean = false,         // atualização intra (sem picos de quadro-chave)
    var ultimoQuadro: Boolean = true,   // mostra sempre o quadro mais novo
    var estatisticas: Boolean = false,  // painel de estatísticas na tela
    var cursor: Boolean = true,         // desenhar o cursor do PC no vídeo
    var compat: Boolean = false,        // MJPEG em vez de H.264/H.265
    var jpeg: Int = 75,                 // qualidade do modo compatível
    // Toque e caneta
    var toque: String = "nativo",       // nativo | mouse | desligado
    var caneta: Boolean = true,         // S Pen com pressão e inclinação
    var curva: Float = 1f,              // curva de pressão (<1 mais macia, >1 mais firme)
    var palma: Boolean = false,         // só a caneta age; dedos ignorados
    var barra: Boolean = true,          // barra lateral de atalhos
    var barraLado: String = "esquerda", // esquerda | direita
    // Conexão
    var porta: Int = 8080,
    var pin: String = "",
    var autoconectar: Boolean = false,
    var ultimoHost: String = ""
) {
    fun salvar(p: SharedPreferences) {
        p.edit()
            .putString("modo", modo).putString("lado", lado)
            .putInt("resolucao", resolucao).putInt("escala", escala)
            .putString("orientacao", orientacao)
            .putString("perfil", perfil).putString("codec", codec)
            .putInt("fps3", fps).putInt("mbps", mbps)
            .putString("taxa", taxa).putInt("cq", cq)
            .putString("velocidade", velocidade).putFloat("gop", gop)
            .putBoolean("intra", intra).putBoolean("ultimoQuadro", ultimoQuadro)
            .putBoolean("estatisticas", estatisticas).putBoolean("cursor", cursor)
            .putBoolean("compat", compat).putInt("jpeg", jpeg)
            .putString("toque", toque).putBoolean("caneta", caneta)
            .putFloat("curva", curva)
            .putBoolean("palma", palma).putBoolean("barra", barra)
            .putString("barraLado", barraLado)
            .putInt("porta3", porta).putString("pin", pin)
            .putBoolean("autoconectar", autoconectar)
            .putString("host", ultimoHost)
            .apply()
    }

    /** Perfis prontos: mudam só as opções de vídeo e desempenho. */
    fun aplicarPerfil(nome: String) {
        perfil = nome
        when (nome) {
            "desenho" -> {      // mínima latência para a S Pen
                codec = "h264"; fps = 60; mbps = 40; taxa = "cbr"
                velocidade = "rapida"; gop = 2f; intra = true; ultimoQuadro = true
                resolucao = 100
            }
            "trabalho" -> {     // texto nítido, rede econômica com tela parada
                codec = "h265"; fps = 60; mbps = 30; taxa = "cq"; cq = 22
                velocidade = "equilibrada"; gop = 4f; intra = false; ultimoQuadro = true
                resolucao = 100
            }
            "video" -> {        // movimento bonito
                codec = "h265"; fps = 60; mbps = 40; taxa = "vbr"
                velocidade = "qualidade"; gop = 2f; intra = false; ultimoQuadro = false
                resolucao = 100
            }
            "economia" -> {     // Wi-Fi fraco ou bateria
                codec = "h265"; fps = 30; mbps = 8; taxa = "vbr"
                velocidade = "rapida"; gop = 2f; intra = true; ultimoQuadro = true
                resolucao = 60
            }
        }
    }

    companion object {
        fun carregar(p: SharedPreferences) = Ajustes(
            modo = p.getString("modo", "estender")!!,
            lado = p.getString("lado", "direita")!!,
            resolucao = p.getInt("resolucao", 100).coerceIn(25, 100),
            escala = p.getInt("escala", 0),
            orientacao = p.getString("orientacao", "auto")!!,
            perfil = p.getString("perfil", "personalizado")!!,
            codec = p.getString("codec", "h264")!!,
            fps = p.getInt("fps3", 60).let { if (it == 0) 0 else it.coerceIn(10, 60) },
            mbps = p.getInt("mbps", 0).coerceIn(0, 150),
            taxa = p.getString("taxa", "cbr")!!,
            cq = p.getInt("cq", 23).coerceIn(15, 40),
            velocidade = p.getString("velocidade", "rapida")!!,
            gop = p.getFloat("gop", 2f).coerceIn(0.5f, 10f),
            intra = p.getBoolean("intra", false),
            ultimoQuadro = p.getBoolean("ultimoQuadro", true),
            estatisticas = p.getBoolean("estatisticas", false),
            cursor = p.getBoolean("cursor", true),
            compat = p.getBoolean("compat", false),
            jpeg = p.getInt("jpeg", 75).coerceIn(30, 95),
            toque = p.getString("toque", "nativo")!!,
            caneta = p.getBoolean("caneta", true),
            curva = p.getFloat("curva", 1f).coerceIn(0.4f, 2.5f),
            palma = p.getBoolean("palma", false),
            barra = p.getBoolean("barra", true),
            barraLado = p.getString("barraLado", "esquerda")!!,
            porta = p.getInt("porta3", 8080).let { if (it in 1..65535) it else 8080 },
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
