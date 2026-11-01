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
    var barraItens: String = "",        // botões da barra (ids separados por vírgula; vazio = todos)
    // Extras
    var som: Boolean = false,           // som do PC no tablet
    var clipboard: Boolean = true,      // área de transferência compartilhada
    var adaptativo: Boolean = false,    // baixa/sobe o bitrate sozinho durante o uso
    // Conexão
    var porta: Int = 8080,
    var pin: String = "",
    var autoconectar: Boolean = false,
    var ultimoHost: String = ""
) {
    /** pre = "" para os ajustes gerais; "pc:<ip>:" para os ajustes de um PC. */
    fun salvar(p: SharedPreferences, pre: String = "") {
        p.edit()
            .putString(pre + "modo", modo).putString(pre + "lado", lado)
            .putInt(pre + "resolucao", resolucao).putInt(pre + "escala", escala)
            .putString(pre + "orientacao", orientacao)
            .putString(pre + "perfil", perfil).putString(pre + "codec", codec)
            .putInt(pre + "fps3", fps).putInt(pre + "mbps", mbps)
            .putString(pre + "taxa", taxa).putInt(pre + "cq", cq)
            .putString(pre + "velocidade", velocidade).putFloat(pre + "gop", gop)
            .putBoolean(pre + "intra", intra).putBoolean(pre + "ultimoQuadro", ultimoQuadro)
            .putBoolean(pre + "estatisticas", estatisticas).putBoolean(pre + "cursor", cursor)
            .putBoolean(pre + "compat", compat).putInt(pre + "jpeg", jpeg)
            .putString(pre + "toque", toque).putBoolean(pre + "caneta", caneta)
            .putFloat(pre + "curva", curva)
            .putBoolean(pre + "palma", palma).putBoolean(pre + "barra", barra)
            .putString(pre + "barraLado", barraLado).putString(pre + "barraItens", barraItens)
            .putBoolean(pre + "som", som).putBoolean(pre + "clipboard", clipboard)
            .putBoolean(pre + "adaptativo", adaptativo)
            .putInt(pre + "porta3", porta).putString(pre + "pin", pin)
            .putBoolean(pre + "autoconectar", autoconectar)
            .putString(pre + "host", ultimoHost)
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

    /** Resumo curto mostrado na tela inicial e no diagnóstico. */
    fun resumo(): String {
        val tela = if (modo == "estender") "Estender" else "Espelhar"
        val cod = if (codec == "h265") "H.265" else "H.264"
        val quadros = if (fps == 0) "fps automático" else "$fps fps"
        val taxaTxt = when (taxa) { "vbr" -> "VBR"; "cq" -> "qualidade $cq"; else -> "CBR" }
        val bitrate = if (mbps == 0) "bitrate automático" else "$mbps Mbps $taxaTxt"
        return "$tela · $cod · $quadros · $bitrate · $resolucao%"
    }

    /** Mudou alguma opção que exige reiniciar a transmissão? */
    fun mesmoVideo(o: Ajustes): Boolean =
        fps == o.fps && mbps == o.mbps && codec == o.codec && taxa == o.taxa &&
            cq == o.cq && velocidade == o.velocidade && gop == o.gop && intra == o.intra &&
            cursor == o.cursor && compat == o.compat && jpeg == o.jpeg

    companion object {
        fun carregar(p: SharedPreferences, pre: String = "") = Ajustes(
            modo = p.getString(pre + "modo", "estender")!!,
            lado = p.getString(pre + "lado", "direita")!!,
            resolucao = p.getInt(pre + "resolucao", 100).coerceIn(25, 100),
            escala = p.getInt(pre + "escala", 0),
            orientacao = p.getString(pre + "orientacao", "auto")!!,
            perfil = p.getString(pre + "perfil", "personalizado")!!,
            codec = p.getString(pre + "codec", "h264")!!,
            fps = p.getInt(pre + "fps3", 60).let { if (it == 0) 0 else it.coerceIn(10, 60) },
            mbps = p.getInt(pre + "mbps", 0).coerceIn(0, 150),
            taxa = p.getString(pre + "taxa", "cbr")!!,
            cq = p.getInt(pre + "cq", 23).coerceIn(15, 40),
            velocidade = p.getString(pre + "velocidade", "rapida")!!,
            gop = p.getFloat(pre + "gop", 2f).coerceIn(0.5f, 10f),
            intra = p.getBoolean(pre + "intra", false),
            ultimoQuadro = p.getBoolean(pre + "ultimoQuadro", true),
            estatisticas = p.getBoolean(pre + "estatisticas", false),
            cursor = p.getBoolean(pre + "cursor", true),
            compat = p.getBoolean(pre + "compat", false),
            jpeg = p.getInt(pre + "jpeg", 75).coerceIn(30, 95),
            toque = p.getString(pre + "toque", "nativo")!!,
            caneta = p.getBoolean(pre + "caneta", true),
            curva = p.getFloat(pre + "curva", 1f).coerceIn(0.4f, 2.5f),
            palma = p.getBoolean(pre + "palma", false),
            barra = p.getBoolean(pre + "barra", true),
            barraLado = p.getString(pre + "barraLado", "esquerda")!!,
            barraItens = p.getString(pre + "barraItens", "")!!,
            som = p.getBoolean(pre + "som", false),
            clipboard = p.getBoolean(pre + "clipboard", true),
            adaptativo = p.getBoolean(pre + "adaptativo", false),
            porta = p.getInt(pre + "porta3", 8080).let { if (it in 1..65535) it else 8080 },
            pin = p.getString(pre + "pin", "")!!,
            autoconectar = p.getBoolean(pre + "autoconectar", false),
            ultimoHost = p.getString(pre + "host", "")!!
        )

        /** Já existem ajustes salvos para esse prefixo (ex.: um PC)? */
        fun existe(p: SharedPreferences, pre: String) = p.contains(pre + "modo")

        val ESCALAS = listOf(100, 125, 150, 175, 200, 225, 250, 300)

        /** Escala do Windows que deixa a interface num tamanho confortável. */
        fun escalaAuto(larguraMaior: Int): Int {
            val alvo = larguraMaior * 100 / 1440
            return ESCALAS.minByOrNull { kotlin.math.abs(it - alvo) } ?: 100
        }
    }
}
