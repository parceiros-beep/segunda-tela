package com.segundatela.app

import android.content.Context
import android.content.SharedPreferences
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.slider.LabelFormatter
import com.google.android.material.slider.Slider
import com.google.android.material.switchmaterial.SwitchMaterial

/**
 * Opções de ajuste, iguais na tela inicial e nos ajustes ao vivo.
 * Cada linha tem uma explicação e a recomendação.
 *
 * aoAlterar: chamado a cada mudança (a tela aplica o que for possível na hora).
 * aoRecarregar: chamado quando um perfil muda tudo de uma vez (a tela redesenha).
 */
class Painel(
    private val ctx: Context,
    private val aj: Ajustes,
    private val prefs: SharedPreferences,
    private val aoAlterar: () -> Unit = {},
    private val aoRecarregar: () -> Unit = {}
) {
    private var lblPerfil: TextView? = null

    private fun salvar() {
        aj.salvar(prefs)
        aoAlterar()
    }

    /** Mexeu numa opção de vídeo: o perfil vira "Personalizado". */
    private fun personalizado() {
        if (aj.perfil == "personalizado") return
        aj.perfil = "personalizado"
        lblPerfil?.text = ctx.getString(R.string.prof_custom)
    }

    private fun par(v: Int) = v / 2 * 2

    // ------------------------------------------------------------ componentes
    /** Linha com o valor atual em azul; tocar abre a lista de opções. */
    fun escolha(pai: LinearLayout, titulo: Int, desc: Int?, itens: List<Pair<String, String>>,
                atual: String, aoMudar: (String) -> Unit): TextView {
        val row = Linhas.linha(ctx, pai, vertical = true)
        row.gravity = Gravity.CENTER_VERTICAL or Gravity.START
        var valor = atual
        val nome = ctx.getString(titulo)
        row.addView(Linhas.texto(ctx, nome, 17f, R.color.text_primary))
        val sub = Linhas.texto(ctx, itens.firstOrNull { it.first == atual }?.second ?: "",
            14f, R.color.accent).apply { setPadding(0, Linhas.dp(ctx, 2), 0, 0) }
        row.addView(sub)
        Linhas.explica(ctx, row, desc)
        row.setOnClickListener {
            val idx = itens.indexOfFirst { it.first == valor }
            MaterialAlertDialogBuilder(ctx)
                .setTitle(nome)
                .setSingleChoiceItems(itens.map { it.second }.toTypedArray(), idx) { d, i ->
                    valor = itens[i].first
                    sub.text = itens[i].second
                    aoMudar(valor)
                    salvar()
                    d.dismiss()
                }
                .setNegativeButton(R.string.cancel, null)
                .show()
        }
        return sub
    }

    /** Título, valor em azul e controle deslizante embaixo. */
    fun deslizante(pai: LinearLayout, titulo: Int, desc: Int?, de: Float, ate: Float,
                   passo: Float, atual: Float, rotulo: (Float) -> String,
                   aoMudar: (Float) -> Unit) {
        val row = Linhas.linha(ctx, pai, vertical = true)
        row.background = null
        // O Slider exige valor alinhado ao passo e dentro da faixa.
        val inicial = (de + Math.round((atual.coerceIn(de, ate) - de) / passo) * passo)
            .coerceIn(de, ate)
        val topo = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        topo.addView(Linhas.texto(ctx, ctx.getString(titulo), 17f, R.color.text_primary),
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val valor = Linhas.texto(ctx, rotulo(inicial), 14f, R.color.accent)
        topo.addView(valor)
        row.addView(topo, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        row.addView(Slider(ctx).apply {
            valueFrom = de; valueTo = ate; stepSize = passo; value = inicial
            labelBehavior = LabelFormatter.LABEL_GONE
            addOnChangeListener { _, x, doUsuario ->
                valor.text = rotulo(x)
                if (doUsuario) { aoMudar(x); salvar() }
            }
        }, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        Linhas.explica(ctx, row, desc)
    }

    /** Título com interruptor à direita; tocar em qualquer lugar liga/desliga. */
    fun chave(pai: LinearLayout, titulo: Int, desc: Int?, atual: Boolean, aoMudar: (Boolean) -> Unit) {
        val row = Linhas.linha(ctx, pai, vertical = true)
        val topo = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        topo.addView(Linhas.texto(ctx, ctx.getString(titulo), 17f, R.color.text_primary),
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val sw = SwitchMaterial(ctx).apply {
            isChecked = atual
            setOnCheckedChangeListener { _, v -> aoMudar(v); salvar() }
        }
        topo.addView(sw)
        row.addView(topo, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        Linhas.explica(ctx, row, desc)
        row.setOnClickListener { sw.toggle() }
    }

    /** FPS: valor livre de 10 a 60, ou Automático (a rede escolhe ao conectar). */
    fun controleFps(pai: LinearLayout, desc: Int?) {
        val row = Linhas.linha(ctx, pai, vertical = true)
        row.background = null
        val topo = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        topo.addView(Linhas.texto(ctx, ctx.getString(R.string.fps), 17f, R.color.text_primary),
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val valor = Linhas.texto(ctx, "", 14f, R.color.accent)
        topo.addView(valor)
        row.addView(topo, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))

        var manual = if (aj.fps in 10..60) aj.fps else 60
        val slider = Slider(ctx).apply {
            valueFrom = 10f; valueTo = 60f; stepSize = 1f
            value = manual.toFloat()
            labelBehavior = LabelFormatter.LABEL_GONE
        }
        val auto = SwitchMaterial(ctx).apply {
            text = ctx.getString(R.string.fps_auto)
            setTextColor(ctx.getColor(R.color.text_primary))
            isChecked = aj.fps == 0
        }
        fun atualizar() {
            if (auto.isChecked) {
                valor.text = ctx.getString(R.string.fps_auto_value, Conexao.fpsAutomatico(ctx))
                slider.isEnabled = false
            } else {
                valor.text = "$manual fps"
                slider.isEnabled = true
            }
        }
        slider.addOnChangeListener { _, x, doUsuario ->
            manual = x.toInt()
            if (doUsuario) {
                if (!auto.isChecked) aj.fps = manual
                personalizado(); salvar()
            }
            atualizar()
        }
        auto.setOnCheckedChangeListener { _, marcado ->
            aj.fps = if (marcado) 0 else manual
            personalizado(); salvar()
            atualizar()
        }
        row.addView(auto)
        row.addView(slider, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        Linhas.explica(ctx, row, desc)
        atualizar()
    }

    // --------------------------------------------------------------- seções
    fun telaOpcoes(pai: LinearLayout, nw: Int, nh: Int) {
        escolha(pai, R.string.opt_mode, R.string.d_mode, listOf(
            "estender" to ctx.getString(R.string.mode_extend),
            "espelhar" to ctx.getString(R.string.mode_mirror)), aj.modo) { aj.modo = it }
        escolha(pai, R.string.opt_side, R.string.d_side, listOf(
            "esquerda" to ctx.getString(R.string.side_left),
            "direita" to ctx.getString(R.string.side_right),
            "acima" to ctx.getString(R.string.side_top)), aj.lado) { aj.lado = it }
        val maior = maxOf(nw, nh); val menor = minOf(nw, nh)
        deslizante(pai, R.string.opt_resolution, R.string.d_resolution, 25f, 100f, 5f,
            aj.resolucao.toFloat(), { v ->
                val pct = v.toInt()
                "$pct% · ${par(maior * pct / 100)}×${par(menor * pct / 100)}"
            }) { aj.resolucao = it.toInt(); personalizado() }
        escolha(pai, R.string.opt_scale, R.string.d_scale,
            listOf("0" to ctx.getString(R.string.auto)) + Ajustes.ESCALAS.map { it.toString() to "$it%" },
            aj.escala.toString()) { aj.escala = it.toInt() }
        escolha(pai, R.string.opt_orientation, R.string.d_orientation, listOf(
            "auto" to ctx.getString(R.string.or_auto),
            "horizontal" to ctx.getString(R.string.or_landscape),
            "vertical" to ctx.getString(R.string.or_portrait)), aj.orientacao) { aj.orientacao = it }
    }

    /** Opções de vídeo: usadas na tela inicial e nos ajustes ao vivo. */
    fun videoOpcoes(pai: LinearLayout) {
        lblPerfil = escolha(pai, R.string.opt_profile, R.string.d_profile, listOf(
            "desenho" to ctx.getString(R.string.prof_draw),
            "trabalho" to ctx.getString(R.string.prof_work),
            "video" to ctx.getString(R.string.prof_video),
            "economia" to ctx.getString(R.string.prof_eco),
            "personalizado" to ctx.getString(R.string.prof_custom)), aj.perfil) { v ->
            if (v != "personalizado") {
                aj.aplicarPerfil(v)
                aoRecarregar()
            } else aj.perfil = v
        }
        escolha(pai, R.string.opt_codec, R.string.d_codec, listOf(
            "h264" to ctx.getString(R.string.codec_h264),
            "h265" to ctx.getString(R.string.codec_h265)), aj.codec) { aj.codec = it; personalizado() }
        controleFps(pai, R.string.d_fps)
        deslizante(pai, R.string.opt_bitrate, R.string.d_bitrate, 0f, 150f, 1f, aj.mbps.toFloat(),
            { x -> if (x < 1f) ctx.getString(R.string.bitrate_auto) else "${x.toInt()} Mbps" }) {
            aj.mbps = if (it < 2f && it >= 1f) 2 else it.toInt(); personalizado()
        }
        escolha(pai, R.string.opt_rate, R.string.d_rate, listOf(
            "cbr" to ctx.getString(R.string.rate_cbr),
            "vbr" to ctx.getString(R.string.rate_vbr),
            "cq" to ctx.getString(R.string.rate_cq)), aj.taxa) { aj.taxa = it; personalizado() }
        deslizante(pai, R.string.opt_cq, R.string.d_cq, 15f, 40f, 1f, aj.cq.toFloat(),
            { x -> ctx.getString(R.string.cq_value, x.toInt()) }) { aj.cq = it.toInt(); personalizado() }
        escolha(pai, R.string.opt_speed, R.string.d_speed, listOf(
            "rapida" to ctx.getString(R.string.speed_fast),
            "equilibrada" to ctx.getString(R.string.speed_balanced),
            "qualidade" to ctx.getString(R.string.speed_quality)), aj.velocidade) {
            aj.velocidade = it; personalizado()
        }
        deslizante(pai, R.string.opt_gop, R.string.d_gop, 0.5f, 10f, 0.5f, aj.gop,
            { x -> ctx.getString(R.string.gop_value, x) }) { aj.gop = it; personalizado() }
        chave(pai, R.string.opt_intra, R.string.d_intra, aj.intra) { aj.intra = it; personalizado() }
        chave(pai, R.string.opt_latest, R.string.d_latest, aj.ultimoQuadro) {
            aj.ultimoQuadro = it; personalizado()
        }
        chave(pai, R.string.opt_stats, R.string.d_stats, aj.estatisticas) { aj.estatisticas = it }
        chave(pai, R.string.opt_cursor, R.string.d_cursor, aj.cursor) { aj.cursor = it; personalizado() }
    }

    fun toqueOpcoes(pai: LinearLayout) {
        escolha(pai, R.string.opt_touch, R.string.d_touch, listOf(
            "nativo" to ctx.getString(R.string.touch_native),
            "mouse" to ctx.getString(R.string.touch_mouse),
            "touchpad" to ctx.getString(R.string.touch_touchpad),
            "mesa" to ctx.getString(R.string.touch_mesa),
            "desligado" to ctx.getString(R.string.touch_off)), aj.toque) { aj.toque = it }
        chave(pai, R.string.opt_pen, R.string.d_pen, aj.caneta) { aj.caneta = it }
        deslizante(pai, R.string.opt_curve, R.string.d_curve, 0.4f, 2.5f, 0.1f, aj.curva,
            { x -> when {
                x < 0.95f -> ctx.getString(R.string.curve_soft, x)
                x > 1.05f -> ctx.getString(R.string.curve_firm, x)
                else -> ctx.getString(R.string.curve_linear) } }) { aj.curva = it }
        chave(pai, R.string.opt_palm, R.string.d_palm, aj.palma) { aj.palma = it }
        chave(pai, R.string.opt_sidebar, R.string.d_sidebar, aj.barra) { aj.barra = it }
        escolha(pai, R.string.opt_sidebar_side, R.string.d_sidebar_side, listOf(
            "esquerda" to ctx.getString(R.string.side_left),
            "direita" to ctx.getString(R.string.side_right)), aj.barraLado) { aj.barraLado = it }
    }

    fun avancadoOpcoes(pai: LinearLayout, mostrarAutoconectar: Boolean) {
        chave(pai, R.string.opt_compat, R.string.d_compat, aj.compat) { aj.compat = it }
        deslizante(pai, R.string.opt_jpeg, R.string.d_jpeg, 30f, 95f, 5f, aj.jpeg.toFloat(),
            { x -> "${x.toInt()}" }) { aj.jpeg = it.toInt() }
        if (mostrarAutoconectar) {
            chave(pai, R.string.opt_autoconnect, R.string.d_autoconnect, aj.autoconectar) {
                aj.autoconectar = it
            }
        }
    }
}
