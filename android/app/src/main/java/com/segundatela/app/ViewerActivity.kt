package com.segundatela.app

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipDrawable
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.segundatela.app.databinding.ActivityViewerBinding
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

class ViewerActivity : AppCompatActivity(), H264View.Listener, MjpegView.Listener {

    private lateinit var b: ActivityViewerBinding
    private val prefs by lazy { getSharedPreferences("segundatela", Context.MODE_PRIVATE) }
    private lateinit var aj: Ajustes
    private val ui = Handler(Looper.getMainLooper())
    private val hideStatus = Runnable { b.status.visibility = View.GONE }

    private var input: InputSender? = null
    private lateinit var tela: Tela
    private var info = ""
    private var host = ""
    private var port = 8080
    private var pathAtual = ""

    // Caneta
    private var canetaPerto = false
    private var canetaEmContato = false

    // Toque nativo
    private val dedos = HashSet<Int>()

    // Modo mouse (gestos)
    private var downX = 0f; private var downY = 0f
    private var downTime = 0L
    private var moved = false
    private var dragging = false
    private var multi = false
    private var multiMoved = false
    private var lastAvgY = 0f
    private var proximoDireito = false
    private val slop by lazy { resources.displayMetrics.density * 10 }
    private val longPress = Runnable {
        if (!multi && !moved) {
            mapSend(downX, downY) { x, y -> input?.down(x, y) }
            dragging = true
            b.root.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        }
    }

    // Touchpad: o dedo move o cursor pelo deslocamento
    private var tpX = 0f; private var tpY = 0f
    private var tpInicioX = 0f; private var tpInicioY = 0f
    private var tpDedos = 0
    private var tpMovido = false
    private var tpInicio = 0L
    private var tpAvgY = 0f

    // Estatísticas
    @Volatile private var rttMs = -1L
    private val pinger = object : Runnable {
        override fun run() {
            input?.ping()
            ui.postDelayed(this, 1000)
        }
    }

    // Som do PC e área de transferência
    private var som: AudioPlayer? = null
    private var ultimoClip: String? = null
    private val ouvinteClip = ClipboardManager.OnPrimaryClipChangedListener { enviarClip() }

    // Bitrate automático durante o uso
    private var mbpsAdaptado = 0
    private var segundosRuins = 0
    private var segundosBons = 0
    private var ultimoAjuste = 0L

    // Modificadores fixos da barra lateral (Ctrl/Shift/Alt pressionados)
    private val modificadores = HashMap<Int, View>()
    private var selfEdit = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.attributes = window.attributes.apply {
            layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
        b = ActivityViewerBinding.inflate(layoutInflater)
        setContentView(b.root)
        aj = Ajustes.carregar(prefs)

        host = intent.getStringExtra("host") ?: run { finish(); return }
        port = intent.getIntExtra("port", 8080)
        pathAtual = intent.getStringExtra("path") ?: run { finish(); return }
        // "Automático" deixa o tablet girar livremente; a transmissão acompanha.
        requestedOrientation = when (aj.orientacao) {
            "horizontal" -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            "vertical" -> ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT
            else -> ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR
        }

        input = InputSender(host, port, aj.pin).also {
            it.clipboard = aj.clipboard
            it.start()
        }

        val view: View
        if (intent.getBooleanExtra("compat", false)) {
            b.h264.visibility = View.GONE
            b.mjpeg.visibility = View.VISIBLE
            b.mjpeg.listener = this
            b.mjpeg.start("http://$host:$port$pathAtual")
            tela = b.mjpeg; view = b.mjpeg
        } else {
            b.h264.listener = this
            b.h264.ultimoQuadro = aj.ultimoQuadro
            b.h264.start(host, port, pathAtual)
            tela = b.h264; view = b.h264
        }
        view.setOnTouchListener { _, e -> onTouch(e); true }
        view.setOnHoverListener { _, e -> onHover(e) }
        view.setOnGenericMotionListener { _, e -> onGeneric(e) }

        input?.aoPing = { ms -> rttMs = ms }
        if (aj.clipboard) {
            input?.aoClip = { t -> runOnUiThread { receberClip(t) } }
            getSystemService(ClipboardManager::class.java).addPrimaryClipChangedListener(ouvinteClip)
        }
        if (aj.som) ligarSom(true)
        montarBarra()
        montarMenu()
        mostrarEstatisticas(aj.estatisticas)
        b.status.text = getString(R.string.connecting)
    }

    // =================================================================== menu
    private fun montarMenu() {
        b.btnSettings.setOnClickListener { abrirMenu(true) }
        b.scrim.setOnClickListener { abrirMenu(false) }
        b.btnDisconnect.setOnClickListener { finish() }
        b.btnKeyboard.setOnClickListener { abrirMenu(false); abrirTeclado() }
        b.btnAjustes.setOnClickListener { abrirAjustesVivo() }
        b.btnDiag.setOnClickListener { copiarDiagnostico() }

        val opcoes = listOf(
            "nativo" to R.string.touch_native, "mouse" to R.string.touch_mouse,
            "touchpad" to R.string.touch_touchpad, "mesa" to R.string.touch_mesa,
            "desligado" to R.string.touch_off)
        for ((valor, rotulo) in opcoes) {
            b.grpToque.addView(Chip(this).apply {
                setChipDrawable(ChipDrawable.createFromAttributes(context, null, 0,
                    com.google.android.material.R.style.Widget_MaterialComponents_Chip_Choice))
                text = getString(rotulo)
                isCheckable = true
                isChecked = aj.toque == valor
                setOnClickListener {
                    input?.touchReset(); dedos.clear()
                    aj.toque = valor; aj.salvar(prefs)
                }
            })
        }
        b.swBarra.isChecked = aj.barra
        b.swBarra.setOnCheckedChangeListener { _, v ->
            aj.barra = v; aj.salvar(prefs)
            b.sidebarWrap.visibility = if (v) View.VISIBLE else View.GONE
        }
        b.swStats.isChecked = aj.estatisticas
        b.swStats.setOnCheckedChangeListener { _, v ->
            aj.estatisticas = v; aj.salvar(prefs); mostrarEstatisticas(v)
        }
        b.swSom.isChecked = aj.som
        b.swSom.setOnCheckedChangeListener { _, v ->
            aj.som = v; aj.salvar(prefs); ligarSom(v)
        }
        b.swPalma.isChecked = aj.palma
        b.swPalma.setOnCheckedChangeListener { _, v -> aj.palma = v; aj.salvar(prefs) }

        // Campo invisível: texto do teclado da tela -> PC
        b.hiddenInput.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
            override fun onTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
            override fun afterTextChanged(s: Editable?) {
                if (selfEdit || s == null) return
                val txt = s.toString()
                if (txt.isNotEmpty()) {
                    input?.text(txt)
                    selfEdit = true; s.clear(); selfEdit = false
                }
            }
        })
        b.hiddenInput.setOnKeyListener { _, code, ev ->
            if (ev.action == KeyEvent.ACTION_DOWN && code == KeyEvent.KEYCODE_DEL) {
                input?.key("BACKSPACE"); true
            } else false
        }
    }

    private fun abrirMenu(abrir: Boolean) {
        b.settingsPanel.visibility = if (abrir) View.VISIBLE else View.GONE
        b.scrim.visibility = if (abrir) View.VISIBLE else View.GONE
        if (abrir) {
            b.lblInfo.text = info.ifEmpty { getString(R.string.connecting) }
            b.status.visibility = View.GONE
            ui.removeCallbacks(hideStatus)
        } else {
            enterImmersive()
        }
    }

    private fun menuAberto() = b.settingsPanel.visibility == View.VISIBLE

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (menuAberto()) abrirMenu(false) else {
            @Suppress("DEPRECATION")
            super.onBackPressed()
        }
    }

    // ============================================================ ajustes ao vivo
    /** Ajustes de vídeo com a transmissão rodando. Ao fechar, reinicia se preciso. */
    private fun abrirAjustesVivo() {
        abrirMenu(false)
        val antes = aj.copy()
        val conteudo = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val p = Linhas.dp(this@ViewerActivity, 8)
            setPadding(p, 0, p, p)
        }
        val rolagem = ScrollView(this).apply { addView(conteudo) }
        fun montar() {
            conteudo.removeAllViews()
            conteudo.addView(Linhas.texto(this, getString(R.string.live_hint), 13f, R.color.text_muted).apply {
                setPadding(Linhas.dp(this@ViewerActivity, 16), Linhas.dp(this@ViewerActivity, 8),
                    Linhas.dp(this@ViewerActivity, 16), Linhas.dp(this@ViewerActivity, 8))
            })
            Painel(this, aj, prefs, aoAlterar = { aplicarInstantaneos() }, aoRecarregar = { montar() })
                .videoOpcoes(conteudo)
        }
        montar()
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.live_title)
            .setView(rolagem)
            .setPositiveButton(R.string.ok, null)
            .setOnDismissListener {
                if (!antes.mesmoVideo(aj)) reiniciarTransmissao()
            }
            .show()
    }

    /** Opções que não precisam reiniciar a transmissão: aplicam na hora. */
    private fun aplicarInstantaneos() {
        b.h264.ultimoQuadro = aj.ultimoQuadro
        mostrarEstatisticas(aj.estatisticas)
    }

    private fun caminhoAtual(): String {
        // Com o bitrate automático ativo, usa o valor ajustado pela rede.
        val base = if (mbpsAdaptado > 0) aj.copy(mbps = mbpsAdaptado) else aj
        return Conexao.caminho(base,
            Conexao.parametros(this, base, host, Conexao.horizontal(this, base)), aj.pin)
    }

    /** Reinicia a transmissão com os ajustes atuais (sem fechar a tela). */
    private fun reiniciarTransmissao() {
        if (aj.compat) {
            Toast.makeText(this, R.string.live_compat, Toast.LENGTH_LONG).show()
            return
        }
        val novo = caminhoAtual()
        if (novo == pathAtual) return
        pathAtual = novo
        mostrarStatus(getString(R.string.applying), false)
        b.h264.reiniciar(novo)
    }

    /** Girou o tablet com "Automático": a transmissão acompanha o novo tamanho. */
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (!aj.compat && aj.orientacao == "auto") reiniciarTransmissao()
    }

    // ================================================ som e área de transferência
    private fun ligarSom(ligar: Boolean) {
        som?.stop()
        som = null
        if (!ligar) return
        som = AudioPlayer(host, port, aj.pin).also {
            it.aoErro = { m -> runOnUiThread { Toast.makeText(this, m, Toast.LENGTH_LONG).show() } }
            it.start()
        }
    }

    /** Copiou no PC: põe na área de transferência do tablet. */
    private fun receberClip(texto: String) {
        ultimoClip = texto
        getSystemService(ClipboardManager::class.java)
            .setPrimaryClip(ClipData.newPlainText("Segunda Tela", texto))
    }

    /** Copiou no tablet: manda para o PC (sem devolver o que veio dele). */
    private fun enviarClip() {
        val clip = getSystemService(ClipboardManager::class.java).primaryClip ?: return
        if (clip.itemCount == 0) return
        val texto = clip.getItemAt(0).coerceToText(this)?.toString() ?: return
        if (texto.isEmpty() || texto == ultimoClip) return
        ultimoClip = texto
        input?.clip(texto)
    }

    // ========================================================= diagnóstico
    private fun copiarDiagnostico() {
        val m = resources.displayMetrics
        val texto = buildString {
            appendLine("Segunda Tela (tablet)")
            appendLine("Conexão: $host:$port")
            appendLine(info)
            appendLine(b.lblStats.text)
            appendLine("Ajustes: ${aj.resumo()}")
            appendLine("Perfil: ${aj.perfil} · taxa ${aj.taxa} · velocidade ${aj.velocidade}")
            appendLine("Toque: ${aj.toque} · caneta ${aj.caneta} · palma ${aj.palma}")
            appendLine("Tela do tablet: ${m.widthPixels}x${m.heightPixels}")
        }
        getSystemService(ClipboardManager::class.java)
            .setPrimaryClip(ClipData.newPlainText("diagnostico", texto))
        Toast.makeText(this, R.string.diag_copied, Toast.LENGTH_SHORT).show()
    }

    // ========================================================= estatísticas
    private fun mostrarEstatisticas(ligar: Boolean) {
        b.lblStats.visibility = if (ligar) View.VISIBLE else View.GONE
        ui.removeCallbacks(pinger)
        // O atraso da rede também alimenta o bitrate automático.
        if (ligar || aj.adaptativo) ui.post(pinger)
    }

    override fun onEstatisticas(e: H264View.Estatisticas) {
        adaptarBitrate(e)
        if (b.lblStats.visibility != View.VISIBLE) return
        val rede = if (rttMs >= 0) "$rttMs ms" else "—"
        b.lblStats.text = String.format(java.util.Locale.US,
            "%dx%d %s  %.0f fps\n%.1f Mbps  rede %s  decod %.0f ms\ndescartados %d\n%s",
            e.w, e.h, e.codec, e.fps, e.mbps, rede, e.decodMs, e.descartados, e.encoder)
    }

    /**
     * Bitrate automático durante o uso: 3 s seguidos com fps abaixo de 80% do
     * pedido, muitos quadros descartados ou atraso alto -> baixa 25%.
     * 30 s estável -> sobe 20% até o valor configurado. Cada ajuste reinicia
     * a transmissão (a imagem pisca), por isso há um intervalo mínimo de 10 s.
     */
    private fun adaptarBitrate(e: H264View.Estatisticas) {
        if (!aj.adaptativo || aj.compat) return
        val agora = android.os.SystemClock.elapsedRealtime()
        if (agora - ultimoAjuste < 10_000) return
        val p = Conexao.parametros(this, aj, host, Conexao.horizontal(this, aj))
        val atual = if (mbpsAdaptado > 0) mbpsAdaptado else p.mbps
        val ruim = e.fps < p.fps * 0.8 || e.descartados > p.fps / 4 || rttMs > 80
        if (ruim) { segundosRuins++; segundosBons = 0 } else { segundosBons++; segundosRuins = 0 }
        val novo = when {
            segundosRuins >= 3 && atual > 4 -> maxOf(4, atual * 3 / 4)
            segundosBons >= 30 && atual < p.mbps -> minOf(p.mbps, atual * 6 / 5 + 1)
            else -> return
        }
        mbpsAdaptado = novo
        segundosRuins = 0; segundosBons = 0
        ultimoAjuste = agora
        reiniciarTransmissao()
        mostrarStatus(getString(R.string.adaptive_changed, novo), true)
    }

    // ======================================================= barra de atalhos
    private fun montarBarra() {
        b.sidebarWrap.visibility = if (aj.barra) View.VISIBLE else View.GONE
        val direita = aj.barraLado == "direita"
        if (direita) {
            // Espelha a barra: fica na borda direita com o puxador por dentro.
            (b.sidebarWrap.layoutParams as android.widget.FrameLayout.LayoutParams).gravity =
                Gravity.END
            b.sidebarWrap.layoutDirection = View.LAYOUT_DIRECTION_RTL
            b.sidebarHandle.scaleX = -1f
            b.btnSettings.layoutParams = (b.btnSettings.layoutParams as
                android.widget.FrameLayout.LayoutParams).apply { gravity = Gravity.TOP or Gravity.START }
        }
        val abre = if (direita) "‹" else "›"
        val fecha = if (direita) "›" else "‹"
        b.sidebarHandle.text = fecha
        b.sidebarHandle.setOnClickListener {
            val aberto = b.sidebarScroll.visibility == View.VISIBLE
            b.sidebarScroll.visibility = if (aberto) View.GONE else View.VISIBLE
            b.sidebarHandle.text = if (aberto) abre else fecha
        }
        var grupo = -1
        for (item in Atalhos.escolhidos(aj)) {
            if (grupo >= 0 && item.grupo != grupo) separador()
            grupo = item.grupo
            when (item.tipo) {
                "teclado" -> tecla(item.texto, item.nome) { abrirTeclado() }
                "mod" -> modificador(item.texto, item.valor.toInt())
                "direito" -> tecla(item.texto, item.nome) { v ->
                    proximoDireito = !proximoDireito
                    v.isActivated = proximoDireito
                }
                else -> atalho(item.texto, item.nome, item.valor)
            }
        }
    }

    private fun tecla(texto: String, desc: String, acao: (View) -> Unit): TextView {
        val d = resources.displayMetrics.density
        val tv = TextView(this).apply {
            text = texto
            contentDescription = desc
            gravity = Gravity.CENTER
            setTextColor(0xFFEDF1F7.toInt())
            textSize = if (texto.length > 4) 11f else 14f
            setBackgroundResource(R.drawable.key_bg)
            layoutParams = LinearLayout.LayoutParams((52 * d).toInt(), (44 * d).toInt()).apply {
                topMargin = (3 * d).toInt(); bottomMargin = (3 * d).toInt()
            }
            setOnClickListener { acao(it) }
            setOnLongClickListener {
                Toast.makeText(context, desc, Toast.LENGTH_SHORT).show(); true
            }
        }
        b.sidebar.addView(tv)
        return tv
    }

    private fun atalho(texto: String, desc: String, combo: String) {
        tecla(texto, desc) { input?.key(combo) }
    }

    private fun modificador(texto: String, vk: Int) {
        val v = tecla(texto, "$texto (fica pressionado)") { v ->
            val ligado = !v.isActivated
            v.isActivated = ligado
            if (ligado) input?.keyDown(vk) else input?.keyUp(vk)
        }
        modificadores[vk] = v
    }

    private fun separador() {
        val d = resources.displayMetrics.density
        b.sidebar.addView(View(this).apply {
            setBackgroundColor(0x22FFFFFF)
            layoutParams = LinearLayout.LayoutParams((36 * d).toInt(), (1 * d).toInt()).apply {
                topMargin = (6 * d).toInt(); bottomMargin = (6 * d).toInt()
            }
        })
    }

    private fun soltarModificadores() {
        for ((vk, v) in modificadores) {
            if (v.isActivated) { input?.keyUp(vk); v.isActivated = false }
        }
    }

    // ================================================================= toque
    private fun ehCaneta(e: MotionEvent, i: Int = 0): Boolean {
        val t = e.getToolType(i)
        return t == MotionEvent.TOOL_TYPE_STYLUS || t == MotionEvent.TOOL_TYPE_ERASER
    }

    private fun onTouch(e: MotionEvent) {
        if (menuAberto()) return
        // Mesa digitalizadora: só a caneta age, sempre.
        if (ehCaneta(e) && (aj.caneta || aj.toque == "mesa")) { onCaneta(e); return }
        if (aj.toque == "mesa" || aj.toque == "desligado") return
        // Rejeição da palma: com a caneta perto da tela, ignora a mão.
        if (canetaPerto || canetaEmContato || (aj.palma && aj.caneta)) return
        when (aj.toque) {
            "nativo" -> toqueNativo(e)
            "mouse" -> toqueMouse(e)
            "touchpad" -> toqueTouchpad(e)
        }
    }

    private fun toqueNativo(e: MotionEvent) {
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> {
                val i = e.actionIndex
                val id = e.getPointerId(i)
                val p = tela.toImage(e.getX(i), e.getY(i)) ?: return
                if (proximoDireito) {
                    input?.rightClick(p.first, p.second)
                    proximoDireito = false
                    return
                }
                dedos.add(id)
                input?.touch('d', id, p.first, p.second)
            }
            MotionEvent.ACTION_MOVE -> {
                val pts = ArrayList<Triple<Int, Float, Float>>(e.pointerCount)
                for (i in 0 until e.pointerCount) {
                    val id = e.getPointerId(i)
                    if (id !in dedos) continue
                    val p = tela.toImage(e.getX(i), e.getY(i)) ?: continue
                    pts.add(Triple(id, p.first, p.second))
                }
                input?.touchMove(pts)
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> {
                val i = e.actionIndex
                val id = e.getPointerId(i)
                if (dedos.remove(id)) {
                    val p = tela.toImage(e.getX(i), e.getY(i)) ?: (0f to 0f)
                    input?.touch('u', id, p.first, p.second)
                }
            }
            MotionEvent.ACTION_CANCEL -> {
                dedos.clear(); input?.touchReset()
            }
        }
    }

    private fun onCaneta(e: MotionEvent) {
        val botoes = botoesCaneta(e)
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                canetaEmContato = true
                if (dedos.isNotEmpty()) { dedos.clear(); input?.touchReset() }
                enviarCaneta('d', e, -1, botoes)
            }
            MotionEvent.ACTION_MOVE -> {
                for (h in 0 until e.historySize) enviarCaneta('m', e, h, botoes)
                enviarCaneta('m', e, -1, botoes)
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                canetaEmContato = false
                enviarCaneta('u', e, -1, botoes)
            }
        }
    }

    private fun onHover(e: MotionEvent): Boolean {
        if (!(aj.caneta || aj.toque == "mesa") || !ehCaneta(e)) return false
        when (e.actionMasked) {
            MotionEvent.ACTION_HOVER_ENTER, MotionEvent.ACTION_HOVER_MOVE -> {
                canetaPerto = true
                enviarCaneta('h', e, -1, botoesCaneta(e))
            }
            MotionEvent.ACTION_HOVER_EXIT -> {
                canetaPerto = false
                enviarCaneta('x', e, -1, 0)
            }
        }
        return true
    }

    /** Mouse/trackpad externo e roda do mouse. */
    private fun onGeneric(e: MotionEvent): Boolean {
        if (e.actionMasked == MotionEvent.ACTION_SCROLL) {
            val p = tela.toImage(e.x, e.y) ?: return false
            val v = e.getAxisValue(MotionEvent.AXIS_VSCROLL)
            if (v != 0f) input?.scroll(p.first, p.second, if (v > 0) 1 else -1)
            return true
        }
        return false
    }

    private fun botoesCaneta(e: MotionEvent): Int {
        var bt = 0
        if (e.buttonState and (MotionEvent.BUTTON_STYLUS_PRIMARY or MotionEvent.BUTTON_SECONDARY) != 0) bt = bt or 1
        if (e.getToolType(0) == MotionEvent.TOOL_TYPE_ERASER) bt = bt or 2
        return bt
    }

    private fun enviarCaneta(estado: Char, e: MotionEvent, hist: Int, botoes: Int) {
        val x = if (hist >= 0) e.getHistoricalX(hist) else e.x
        val y = if (hist >= 0) e.getHistoricalY(hist) else e.y
        val p = tela.toImage(x, y) ?: return
        val bruta = if (hist >= 0) e.getHistoricalPressure(hist) else e.pressure
        val pressao = Math.pow(bruta.coerceIn(0f, 1f).toDouble(), aj.curva.toDouble()).toFloat()
        val tilt = e.getAxisValue(MotionEvent.AXIS_TILT)            // radianos
        val orient = e.getAxisValue(MotionEvent.AXIS_ORIENTATION)   // radianos
        val graus = Math.toDegrees(tilt.toDouble())
        val tx = (graus * sin(orient.toDouble())).toFloat()
        val ty = (-graus * cos(orient.toDouble())).toFloat()
        input?.pen(estado, p.first, p.second, pressao, tx, ty, botoes)
    }

    // -------- modo mouse (tocar = clique, segurar = arrastar, 2 dedos = rolar)
    private fun toqueMouse(e: MotionEvent) {
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                multi = false; multiMoved = false; moved = false; dragging = false
                downX = e.x; downY = e.y; downTime = System.currentTimeMillis()
                mapSend(e.x, e.y) { x, y -> input?.move(x, y) }
                ui.postDelayed(longPress, 500)
            }
            MotionEvent.ACTION_POINTER_DOWN -> {
                multi = true
                ui.removeCallbacks(longPress)
                lastAvgY = avgY(e)
            }
            MotionEvent.ACTION_MOVE -> {
                if (multi) {
                    val ay = avgY(e)
                    val dy = ay - lastAvgY
                    if (abs(dy) > slop * 0.6f) {
                        val ticks = (dy / slop).toInt()
                        if (ticks != 0) {
                            mapSend(e.x, e.y) { x, y -> input?.scroll(x, y, ticks) }
                            lastAvgY = ay; multiMoved = true
                        }
                    }
                } else {
                    mapSend(e.x, e.y) { x, y -> input?.move(x, y) }
                    if (!moved && (abs(e.x - downX) > slop || abs(e.y - downY) > slop)) {
                        moved = true
                        if (!dragging) ui.removeCallbacks(longPress)
                    }
                }
            }
            MotionEvent.ACTION_POINTER_UP -> {
                if (multi && !multiMoved) {
                    mapSend(downX, downY) { x, y -> input?.rightClick(x, y) }
                    multiMoved = true
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                ui.removeCallbacks(longPress)
                if (!multi) {
                    if (dragging) {
                        mapSend(e.x, e.y) { x, y -> input?.up(x, y) }
                    } else if (!moved && System.currentTimeMillis() - downTime < 400) {
                        if (proximoDireito) {
                            mapSend(downX, downY) { x, y -> input?.rightClick(x, y) }
                            proximoDireito = false
                        } else {
                            mapSend(downX, downY) { x, y -> input?.down(x, y); input?.up(x, y) }
                        }
                    }
                }
                multi = false; dragging = false; moved = false
            }
        }
    }

    // -------- touchpad: o cursor anda pelo deslocamento do dedo, como um trackpad
    /** Sensibilidade: deslizar a largura da tela do tablet anda 1,4× a largura do PC. */
    private val sensibilidadeTouchpad = 1.4f

    private fun toqueTouchpad(e: MotionEvent) {
        val area = tela as View
        val vw = area.width.coerceAtLeast(1).toFloat()
        val vh = area.height.coerceAtLeast(1).toFloat()
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                tpX = e.x; tpY = e.y; tpInicioX = e.x; tpInicioY = e.y
                tpDedos = 1; tpMovido = false; tpInicio = System.currentTimeMillis()
            }
            MotionEvent.ACTION_POINTER_DOWN -> {
                tpDedos = maxOf(tpDedos, e.pointerCount)
                tpAvgY = avgY(e)
            }
            MotionEvent.ACTION_MOVE -> {
                if (e.pointerCount >= 2) {
                    // Dois dedos arrastando = rolagem
                    val ay = avgY(e)
                    val dy = ay - tpAvgY
                    if (abs(dy) > slop) {
                        val ticks = (dy / slop).toInt()
                        if (ticks != 0) {
                            input?.wheelHere(ticks)
                            tpAvgY = ay; tpMovido = true
                        }
                    }
                } else {
                    val dx = e.x - tpX; val dy = e.y - tpY
                    if (dx != 0f || dy != 0f) {
                        input?.relMove(dx / vw * sensibilidadeTouchpad, dy / vh * sensibilidadeTouchpad)
                        tpX = e.x; tpY = e.y
                    }
                    if (!tpMovido && (abs(e.x - tpInicioX) > slop || abs(e.y - tpInicioY) > slop)) {
                        tpMovido = true
                    }
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                // Toque rápido sem arrastar = clique (dois dedos = botão direito)
                val rapido = System.currentTimeMillis() - tpInicio < 250
                if (!tpMovido && rapido) input?.clickHere(right = tpDedos >= 2)
                tpDedos = 0
            }
        }
    }

    private fun avgY(e: MotionEvent): Float {
        var sum = 0f
        for (i in 0 until e.pointerCount) sum += e.getY(i)
        return sum / e.pointerCount
    }

    private inline fun mapSend(px: Float, py: Float, send: (Float, Float) -> Unit) {
        val p = tela.toImage(px, py) ?: return
        send(p.first, p.second)
    }

    // ================================================================ teclado
    private fun abrirTeclado() {
        val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        b.hiddenInput.requestFocus()
        imm.showSoftInput(b.hiddenInput, InputMethodManager.SHOW_FORCED)
    }

    /** Teclado físico (Book Cover Keyboard, Bluetooth): tecla por tecla no PC. */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (Teclas.fisico(event)) {
            val vk = Teclas.vk(event.keyCode)
            if (vk != null) {
                when (event.action) {
                    KeyEvent.ACTION_DOWN -> input?.keyDown(vk)
                    KeyEvent.ACTION_UP -> input?.keyUp(vk)
                }
                return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

    // ================================================================ status
    private fun enterImmersive() {
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_FULLSCREEN
                or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) enterImmersive()
    }

    private fun mostrarStatus(txt: String, esconder: Boolean) {
        if (menuAberto()) return
        b.status.text = txt
        b.status.visibility = View.VISIBLE
        ui.removeCallbacks(hideStatus)
        if (esconder) ui.postDelayed(hideStatus, 2500)
    }

    override fun onConnected(info: String) {
        this.info = info
        mostrarStatus("• $info", true)
    }

    override fun onConnected() = onConnected(getString(R.string.connected_compat))

    override fun onDisconnected(reason: String) {
        dedos.clear()
        mostrarStatus(getString(R.string.reconnecting, reason), false)
    }

    override fun onStats(fps: Double) {
        if (b.status.visibility == View.VISIBLE && b.status.text.startsWith("•")) {
            b.status.text = String.format("• %s — %.0f fps", info, fps)
        }
    }

    override fun onFatal(msg: String) {
        mostrarStatus(msg, false)
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
    }

    override fun onPause() {
        super.onPause()
        soltarModificadores()
        input?.touchReset()
    }

    override fun onDestroy() {
        ui.removeCallbacks(pinger)
        som?.stop()
        if (aj.clipboard) {
            getSystemService(ClipboardManager::class.java).removePrimaryClipChangedListener(ouvinteClip)
        }
        b.h264.stop()
        b.mjpeg.stop()
        soltarModificadores()
        input?.touchReset()
        input?.stop()
        super.onDestroy()
    }
}
