package com.segundatela.app

import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.util.DisplayMetrics
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.slider.LabelFormatter
import com.google.android.material.slider.Slider
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.switchmaterial.SwitchMaterial
import com.segundatela.app.databinding.ActivityConnectBinding
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class ConnectActivity : AppCompatActivity(), NsdDiscovery.Listener {

    private lateinit var b: ActivityConnectBinding
    private val prefs by lazy { getSharedPreferences("segundatela", Context.MODE_PRIVATE) }
    private lateinit var aj: Ajustes
    private var discovery: NsdDiscovery? = null
    private val seen = HashSet<String>()
    @Volatile private var usbOk = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityConnectBinding.inflate(layoutInflater)
        setContentView(b.root)
        aj = Ajustes.carregar(prefs)

        b.editHost.setText(aj.ultimoHost)
        b.editPort.setText(aj.porta.toString())
        b.editPin.setText(aj.pin)
        montarOpcoes()

        b.btnConnect.setOnClickListener { conectar(b.editHost.text.toString().trim()) }
        b.editHost.setOnEditorActionListener { _, id, _ ->
            if (id == EditorInfo.IME_ACTION_GO) {
                conectar(b.editHost.text.toString().trim()); true
            } else false
        }
        b.btnUsb.setOnClickListener { conectar("127.0.0.1") }

        if (aj.autoconectar && aj.ultimoHost.isNotBlank()) {
            b.root.post { conectar(aj.ultimoHost) }
        }
    }

    // ============================================================== opções
    private lateinit var lblPerfil: TextView

    private fun montarOpcoes() {
        // ---------------- Tela
        val tela = b.grpTela
        escolha(tela, R.string.opt_mode, listOf(
            "estender" to getString(R.string.mode_extend),
            "espelhar" to getString(R.string.mode_mirror)), aj.modo) { aj.modo = it }
        escolha(tela, R.string.opt_side, listOf(
            "esquerda" to getString(R.string.side_left),
            "direita" to getString(R.string.side_right),
            "acima" to getString(R.string.side_top)), aj.lado) { aj.lado = it }
        val (lw, lh) = tamanhoNativo()
        val maior = maxOf(lw, lh); val menor = minOf(lw, lh)
        deslizante(tela, R.string.opt_resolution, 25f, 100f, 5f, aj.resolucao.toFloat(),
            { v -> val pct = v.toInt()
                "$pct% · ${par(maior * pct / 100)}×${par(menor * pct / 100)}" }) {
            aj.resolucao = it.toInt(); personalizado()
        }
        escolha(tela, R.string.opt_scale,
            listOf("0" to getString(R.string.auto)) +
                Ajustes.ESCALAS.map { it.toString() to "$it%" },
            aj.escala.toString()) { aj.escala = it.toInt() }
        escolha(tela, R.string.opt_orientation, listOf(
            "auto" to getString(R.string.or_auto),
            "horizontal" to getString(R.string.or_landscape),
            "vertical" to getString(R.string.or_portrait)), aj.orientacao) { aj.orientacao = it }

        // ---------------- Vídeo e desempenho
        val v = b.grpVideo
        lblPerfil = escolha(v, R.string.opt_profile, listOf(
            "desenho" to getString(R.string.prof_draw),
            "trabalho" to getString(R.string.prof_work),
            "video" to getString(R.string.prof_video),
            "economia" to getString(R.string.prof_eco),
            "personalizado" to getString(R.string.prof_custom)), aj.perfil) {
            if (it != "personalizado") {
                aj.aplicarPerfil(it); aj.salvar(prefs)
                recreate()  // mostra os valores do perfil
            } else aj.perfil = it
        }
        dica(v, R.string.profile_hint)
        escolha(v, R.string.opt_codec, listOf(
            "h264" to getString(R.string.codec_h264),
            "h265" to getString(R.string.codec_h265)), aj.codec) { aj.codec = it; personalizado() }
        escolha(v, R.string.fps, listOf(30, 60, 90, 120).map { it.toString() to "$it fps" },
            aj.fps.toString()) { aj.fps = it.toInt(); personalizado() }
        dica(v, R.string.fps_hint)
        deslizante(v, R.string.opt_bitrate, 0f, 150f, 1f, aj.mbps.toFloat(),
            { x -> if (x < 1f) getString(R.string.bitrate_auto) else "${x.toInt()} Mbps" }) {
            aj.mbps = if (it < 2f && it >= 1f) 2 else it.toInt(); personalizado()
        }
        escolha(v, R.string.opt_rate, listOf(
            "cbr" to getString(R.string.rate_cbr),
            "vbr" to getString(R.string.rate_vbr),
            "cq" to getString(R.string.rate_cq)), aj.taxa) { aj.taxa = it; personalizado() }
        dica(v, R.string.rate_hint)
        deslizante(v, R.string.opt_cq, 15f, 40f, 1f, aj.cq.toFloat(),
            { x -> getString(R.string.cq_value, x.toInt()) }) { aj.cq = it.toInt(); personalizado() }
        escolha(v, R.string.opt_speed, listOf(
            "rapida" to getString(R.string.speed_fast),
            "equilibrada" to getString(R.string.speed_balanced),
            "qualidade" to getString(R.string.speed_quality)), aj.velocidade) {
            aj.velocidade = it; personalizado()
        }
        deslizante(v, R.string.opt_gop, 0.5f, 10f, 0.5f, aj.gop,
            { x -> getString(R.string.gop_value, x) }) { aj.gop = it; personalizado() }
        chave(v, R.string.opt_intra, aj.intra) { aj.intra = it; personalizado() }
        chave(v, R.string.opt_latest, aj.ultimoQuadro) { aj.ultimoQuadro = it; personalizado() }
        chave(v, R.string.opt_stats, aj.estatisticas) { aj.estatisticas = it }
        chave(v, R.string.opt_cursor, aj.cursor) { aj.cursor = it }

        // ---------------- Toque e caneta
        val toque = b.grpToque
        escolha(toque, R.string.opt_touch, listOf(
            "nativo" to getString(R.string.touch_native),
            "mouse" to getString(R.string.touch_mouse),
            "desligado" to getString(R.string.touch_off)), aj.toque) { aj.toque = it }
        chave(toque, R.string.opt_pen, aj.caneta) { aj.caneta = it }
        deslizante(toque, R.string.opt_curve, 0.4f, 2.5f, 0.1f, aj.curva,
            { x -> when {
                x < 0.95f -> getString(R.string.curve_soft, x)
                x > 1.05f -> getString(R.string.curve_firm, x)
                else -> getString(R.string.curve_linear) } }) { aj.curva = it }
        chave(toque, R.string.opt_palm, aj.palma) { aj.palma = it }
        chave(toque, R.string.opt_sidebar, aj.barra) { aj.barra = it }
        escolha(toque, R.string.opt_sidebar_side, listOf(
            "esquerda" to getString(R.string.side_left),
            "direita" to getString(R.string.side_right)), aj.barraLado) { aj.barraLado = it }

        // ---------------- Avançado
        val av = b.grpAvancado
        chave(av, R.string.opt_compat, aj.compat) { aj.compat = it }
        deslizante(av, R.string.opt_jpeg, 30f, 95f, 5f, aj.jpeg.toFloat(),
            { x -> "${x.toInt()}" }) { aj.jpeg = it.toInt() }
        chave(av, R.string.opt_autoconnect, aj.autoconectar) { aj.autoconectar = it }
    }

    /** Mexeu numa opção de vídeo: o perfil vira "Personalizado". */
    private fun personalizado() {
        if (aj.perfil == "personalizado") return
        aj.perfil = "personalizado"
        if (::lblPerfil.isInitialized) lblPerfil.text = getString(R.string.prof_custom)
    }

    private fun par(v: Int) = v / 2 * 2
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    // ------------------------------------------------ linhas no estilo One UI
    /** Divisória entre linhas do mesmo cartão (recuada nas laterais). */
    private fun divisor(pai: LinearLayout) {
        if (pai.childCount == 0) return
        pai.addView(View(this).apply {
            setBackgroundColor(getColor(R.color.divider))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(1)).apply {
                marginStart = dp(20); marginEnd = dp(20)
            }
        })
    }

    private fun texto(t: String, sp: Float, cor: Int) = TextView(this).apply {
        text = t
        textSize = sp
        setTextColor(getColor(cor))
    }

    private fun linhaBase(pai: LinearLayout, vertical: Boolean): LinearLayout {
        divisor(pai)
        val row = LinearLayout(this).apply {
            orientation = if (vertical) LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            minimumHeight = dp(64)
            setPadding(dp(20), dp(14), dp(20), dp(14))
            setBackgroundResource(R.drawable.row_bg)
        }
        pai.addView(row)
        return row
    }

    private fun dica(pai: LinearLayout, res: Int) {
        pai.addView(texto(getString(res), 13f, R.color.text_muted).apply {
            setPadding(dp(20), 0, dp(20), dp(12))
        })
    }

    /** Linha com o valor atual em azul; tocar abre a lista de opções. */
    private fun escolha(pai: LinearLayout, titulo: Int, itens: List<Pair<String, String>>,
                        atual: String, aoMudar: (String) -> Unit): TextView {
        val row = linhaBase(pai, vertical = true)
        row.gravity = android.view.Gravity.CENTER_VERTICAL or android.view.Gravity.START
        var valor = atual
        val nome = getString(titulo)
        row.addView(texto(nome, 17f, R.color.text_primary))
        val sub = texto(itens.firstOrNull { it.first == atual }?.second ?: "", 14f, R.color.accent)
            .apply { setPadding(0, dp(2), 0, 0) }
        row.addView(sub)
        row.setOnClickListener {
            val idx = itens.indexOfFirst { it.first == valor }
            MaterialAlertDialogBuilder(this)
                .setTitle(nome)
                .setSingleChoiceItems(itens.map { it.second }.toTypedArray(), idx) { d, i ->
                    valor = itens[i].first
                    sub.text = itens[i].second
                    aoMudar(valor)
                    aj.salvar(prefs)
                    d.dismiss()
                }
                .setNegativeButton(R.string.cancel, null)
                .show()
        }
        return sub
    }

    /** Linha com título, valor em azul e controle deslizante embaixo. */
    private fun deslizante(pai: LinearLayout, titulo: Int, de: Float, ate: Float, passo: Float,
                           atual: Float, rotulo: (Float) -> String, aoMudar: (Float) -> Unit) {
        val row = linhaBase(pai, vertical = true)
        row.background = null
        // O Slider exige valor alinhado ao passo e dentro da faixa.
        val inicial = (de + Math.round((atual.coerceIn(de, ate) - de) / passo) * passo)
            .coerceIn(de, ate)
        val topo = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        topo.addView(texto(getString(titulo), 17f, R.color.text_primary),
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val valor = texto(rotulo(inicial), 14f, R.color.accent)
        topo.addView(valor)
        row.addView(topo, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        row.addView(Slider(this).apply {
            valueFrom = de; valueTo = ate; stepSize = passo; value = inicial
            labelBehavior = LabelFormatter.LABEL_GONE
            addOnChangeListener { _, x, doUsuario ->
                valor.text = rotulo(x)
                if (doUsuario) { aoMudar(x); aj.salvar(prefs) }
            }
        }, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
    }

    /** Linha com interruptor à direita; tocar em qualquer lugar liga/desliga. */
    private fun chave(pai: LinearLayout, titulo: Int, atual: Boolean, aoMudar: (Boolean) -> Unit) {
        val row = linhaBase(pai, vertical = false)
        row.addView(texto(getString(titulo), 17f, R.color.text_primary),
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val sw = SwitchMaterial(this).apply {
            isChecked = atual
            setOnCheckedChangeListener { _, v -> aoMudar(v); aj.salvar(prefs) }
        }
        row.addView(sw)
        row.setOnClickListener { sw.toggle() }
    }

    // ====================================================== tamanho da tela
    private fun tamanhoNativo(): Pair<Int, Int> {
        return if (Build.VERSION.SDK_INT >= 30) {
            val r = windowManager.maximumWindowMetrics.bounds
            r.width() to r.height()
        } else {
            val m = DisplayMetrics()
            @Suppress("DEPRECATION")
            windowManager.defaultDisplay.getRealMetrics(m)
            m.widthPixels to m.heightPixels
        }
    }

    // ============================================================ descoberta
    override fun onStart() {
        super.onStart()
        seen.clear()
        b.listPcs.removeAllViews()
        b.rowSearching.visibility = View.VISIBLE
        discovery = NsdDiscovery(this).also { it.listener = this; it.start() }
        verificarUsb()
        b.lblNet.text = try { NetInfo.describe(NetInfo.read(this)) } catch (_: Exception) {
            getString(R.string.tagline)
        }
    }

    override fun onStop() {
        super.onStop()
        discovery?.stop()
        discovery = null
    }

    /** Servidor alcançável por 127.0.0.1 = tablet no cabo com adb reverse. */
    private fun verificarUsb() {
        val porta = portaDigitada()
        thread(isDaemon = true) {
            val ok = try {
                val c = URL("http://127.0.0.1:$porta/status").openConnection() as HttpURLConnection
                c.connectTimeout = 800; c.readTimeout = 800
                val r = c.responseCode == 200
                c.disconnect(); r
            } catch (_: Exception) { false }
            usbOk = ok
            runOnUiThread {
                b.lblUsb.text = getString(if (ok) R.string.usb_on else R.string.usb_off)
                b.lblUsb.setTextColor(getColor(if (ok) R.color.ok else R.color.text_muted))
            }
        }
    }

    override fun onFound(device: NsdDiscovery.Device) {
        val key = "${device.host}:${device.port}"
        if (!seen.add(key)) return
        b.rowSearching.visibility = View.GONE
        val lista = b.listPcs
        divisor(lista)
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            minimumHeight = dp(72)
            setPadding(dp(20), dp(12), dp(20), dp(12))
            setBackgroundResource(R.drawable.row_bg)
        }
        row.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_monitor)
            setBackgroundResource(R.drawable.icon_circle)
            setPadding(dp(10), dp(10), dp(10), dp(10))
        }, LinearLayout.LayoutParams(dp(44), dp(44)))
        val textos = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), 0, 0, 0)
        }
        textos.addView(texto(device.name, 17f, R.color.text_primary))
        textos.addView(texto(getString(R.string.pc_ready, device.host), 14f, R.color.text_muted))
        row.addView(textos, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        row.addView(ImageView(this).apply { setImageResource(R.drawable.ic_chevron) },
            LinearLayout.LayoutParams(dp(24), dp(24)))
        row.setOnClickListener {
            b.editHost.setText(device.host)
            if (device.port in 1..65535) b.editPort.setText(device.port.toString())
            conectar(device.host)
        }
        lista.addView(row)
    }

    // ============================================================== conectar
    private fun conectar(host: String) {
        if (host.isEmpty()) {
            Toast.makeText(this, getString(R.string.err_host), Toast.LENGTH_SHORT).show()
            return
        }
        aj.porta = portaDigitada()
        b.editPort.setText(aj.porta.toString())
        aj.pin = b.editPin.text.toString().trim()
        if (host != "127.0.0.1") aj.ultimoHost = host
        aj.salvar(prefs)

        // Orientação da sessão e tamanho do monitor = tela do tablet.
        val (nw, nh) = tamanhoNativo()
        val maior = maxOf(nw, nh); val menor = minOf(nw, nh)
        val horizontal = when (aj.orientacao) {
            "horizontal" -> true
            "vertical" -> false
            else -> resources.configuration.orientation != Configuration.ORIENTATION_PORTRAIT
        }
        val w = par((if (horizontal) maior else menor) * aj.resolucao / 100)
        val h = par((if (horizontal) menor else maior) * aj.resolucao / 100)
        val escala = if (aj.escala > 0) aj.escala else Ajustes.escalaAuto(maxOf(w, h))

        val mbps = if (aj.mbps > 0) aj.mbps else {
            // ~0,1 bit por pixel; limitado pela velocidade do Wi-Fi.
            val bpp = if (aj.codec == "h265") 14_000_000L else 10_000_000L
            val ideal = (w.toLong() * h * aj.fps / bpp).toInt().coerceIn(6, 60)
            if (host == "127.0.0.1") ideal else {
                val link = try { NetInfo.read(this).linkMbps } catch (_: Exception) { 0 }
                if (link > 0) minOf(ideal, maxOf(6, link * 2 / 5)) else ideal
            }
        }

        val path = StringBuilder()
        if (aj.compat) {
            path.append("/stream?fps=${minOf(aj.fps, 30)}&quality=${aj.jpeg}")
        } else {
            path.append("/video?fps=${aj.fps}&kbps=${mbps * 1000}&codec=${aj.codec}")
            path.append("&taxa=${aj.taxa}&cq=${aj.cq}&vel=${aj.velocidade}")
            path.append("&gop=${aj.gop}&intra=${if (aj.intra) 1 else 0}")
        }
        path.append("&cursor=${if (aj.cursor) 1 else 0}")
        path.append("&w=$w&h=$h&modo=${aj.modo}&lado=${aj.lado}&escala=$escala")
        if (aj.pin.isNotEmpty()) path.append("&pin=${aj.pin}")

        val abrir = Intent(this, ViewerActivity::class.java)
            .putExtra("host", host)
            .putExtra("port", aj.porta)
            .putExtra("path", path.toString())
            .putExtra("compat", aj.compat)
            .putExtra("orient", if (horizontal) "h" else "v")
        testarEAbrir(host, aj.porta, abrir)
    }

    private fun portaDigitada(): Int {
        val p = b.editPort.text.toString().trim().toIntOrNull() ?: 8080
        return if (p in 1..65535) p else 8080
    }

    /** Confere se o servidor responde antes de abrir a tela; explica se não. */
    private fun testarEAbrir(host: String, porta: Int, abrir: Intent) {
        b.btnConnect.isEnabled = false
        b.btnConnect.text = getString(R.string.checking)
        thread(isDaemon = true) {
            val erro: String? = try {
                val c = URL("http://$host:$porta/status").openConnection() as HttpURLConnection
                c.connectTimeout = 2500; c.readTimeout = 2500
                val code = c.responseCode
                c.disconnect()
                if (code == 200) null else "HTTP $code"
            } catch (e: Exception) { e.javaClass.simpleName + ": " + (e.message ?: "") }
            runOnUiThread {
                b.btnConnect.isEnabled = true
                b.btnConnect.text = getString(R.string.connect)
                if (erro == null) {
                    startActivity(abrir)
                    return@runOnUiThread
                }
                val usb = host == "127.0.0.1"
                val msg = if (usb) getString(R.string.err_usb, porta)
                          else getString(R.string.err_wifi, host, porta)
                MaterialAlertDialogBuilder(this)
                    .setTitle(R.string.err_title)
                    .setMessage(msg)
                    .setPositiveButton(R.string.ok, null)
                    .setNeutralButton(R.string.try_anyway) { _, _ -> startActivity(abrir) }
                    .show()
            }
        }
    }
}
