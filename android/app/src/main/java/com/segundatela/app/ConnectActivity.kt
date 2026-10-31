package com.segundatela.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.segundatela.app.databinding.ActivityConnectBinding
import org.json.JSONArray
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
        atualizarResumo()

        b.btnConnect.setOnClickListener { conectar(b.editHost.text.toString().trim()) }
        b.editHost.setOnEditorActionListener { _, id, _ ->
            if (id == EditorInfo.IME_ACTION_GO) {
                conectar(b.editHost.text.toString().trim()); true
            } else false
        }
        b.btnUsb.setOnClickListener { conectar("127.0.0.1") }
        b.btnTestar.setOnClickListener { testarRede() }
        b.lblAtualizar.setOnClickListener {
            startActivity(Intent(Intent.ACTION_VIEW,
                Uri.parse("https://github.com/parceiros-beep/segunda-tela/releases/latest")))
        }

        // Aberto pelo botão do painel rápido: conecta direto no último PC.
        if (intent.getBooleanExtra("conectarAgora", false)) {
            b.root.post { conectar(aj.ultimoHost) }
        } else if (aj.autoconectar && aj.ultimoHost.isNotBlank()) {
            b.root.post { conectar(aj.ultimoHost) }
        }
    }

    // ============================================================== opções
    private fun montarOpcoes() {
        val painel = Painel(this, aj, prefs,
            aoAlterar = { atualizarResumo() },
            aoRecarregar = { recreate() })
        val (nw, nh) = Conexao.nativo(this)
        painel.telaOpcoes(b.grpTela, nw, nh)
        painel.videoOpcoes(b.grpVideo)
        painel.toqueOpcoes(b.grpToque)
        painel.avancadoOpcoes(b.grpAvancado, mostrarAutoconectar = true)
    }

    private fun atualizarResumo() {
        b.lblResumo.text = aj.resumo()
    }

    // ============================================================ descoberta
    override fun onStart() {
        super.onStart()
        seen.clear()
        b.listPcs.removeAllViews()
        b.rowSearching.visibility = View.VISIBLE
        discovery = NsdDiscovery(this).also { it.listener = this; it.start() }
        verificarUsb()
        verificarAtualizacao()
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
        Linhas.divisor(this, lista)
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            minimumHeight = Linhas.dp(this@ConnectActivity, 72)
            val h = Linhas.dp(this@ConnectActivity, 20)
            val v = Linhas.dp(this@ConnectActivity, 12)
            setPadding(h, v, h, v)
            setBackgroundResource(R.drawable.row_bg)
        }
        row.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_monitor)
            setBackgroundResource(R.drawable.icon_circle)
            val p = Linhas.dp(this@ConnectActivity, 10)
            setPadding(p, p, p, p)
        }, LinearLayout.LayoutParams(Linhas.dp(this, 44), Linhas.dp(this, 44)))
        val textos = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(Linhas.dp(this@ConnectActivity, 16), 0, 0, 0)
        }
        textos.addView(Linhas.texto(this, device.name, 17f, R.color.text_primary))
        textos.addView(Linhas.texto(this, getString(R.string.pc_ready, device.host), 14f,
            R.color.text_muted))
        row.addView(textos, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        row.addView(ImageView(this).apply { setImageResource(R.drawable.ic_chevron) },
            LinearLayout.LayoutParams(Linhas.dp(this, 24), Linhas.dp(this, 24)))
        row.setOnClickListener {
            b.editHost.setText(device.host)
            if (device.port in 1..65535) b.editPort.setText(device.port.toString())
            conectar(device.host)
        }
        lista.addView(row)
    }

    // ========================================================= teste de rede
    /** Mede o atraso até o PC e sugere o perfil que combina com a rede. */
    private fun testarRede() {
        val host = b.editHost.text.toString().trim().ifEmpty { aj.ultimoHost }
        if (host.isEmpty()) {
            Toast.makeText(this, getString(R.string.err_host), Toast.LENGTH_SHORT).show()
            return
        }
        val porta = portaDigitada()
        b.btnTestar.isEnabled = false
        thread(isDaemon = true) {
            val tempos = ArrayList<Long>()
            repeat(5) {
                val t0 = System.nanoTime()
                try {
                    val c = URL("http://$host:$porta/status").openConnection() as HttpURLConnection
                    c.connectTimeout = 2000; c.readTimeout = 2000
                    if (c.responseCode == 200) tempos.add((System.nanoTime() - t0) / 1_000_000)
                    c.disconnect()
                } catch (_: Exception) {}
            }
            val rtt = tempos.sorted().getOrNull(tempos.size / 2)
            val banda = try { NetInfo.read(this).band } catch (_: Exception) { "—" }
            val usb = host == "127.0.0.1"
            val sugerido = when {
                rtt == null -> null
                usb -> "desenho"
                rtt <= 5 && (banda == "5 GHz" || banda == "6 GHz") -> "desenho"
                rtt <= 15 -> "trabalho"
                else -> "economia"
            }
            runOnUiThread {
                b.btnTestar.isEnabled = true
                if (rtt == null || sugerido == null) {
                    MaterialAlertDialogBuilder(this)
                        .setTitle(R.string.test_net_title)
                        .setMessage(getString(R.string.test_net_fail, host, porta))
                        .setPositiveButton(R.string.ok, null)
                        .show()
                    return@runOnUiThread
                }
                val rede = if (usb) getString(R.string.test_net_usb) else "$banda · $rtt ms"
                MaterialAlertDialogBuilder(this)
                    .setTitle(R.string.test_net_title)
                    .setMessage(getString(R.string.test_net_result, rede, nomePerfil(sugerido)))
                    .setPositiveButton(R.string.test_apply) { _, _ ->
                        aj.aplicarPerfil(sugerido)
                        aj.salvar(prefs)
                        recreate()
                    }
                    .setNegativeButton(R.string.cancel, null)
                    .show()
            }
        }
    }

    private fun nomePerfil(p: String) = getString(when (p) {
        "desenho" -> R.string.prof_draw
        "trabalho" -> R.string.prof_work
        "video" -> R.string.prof_video
        "economia" -> R.string.prof_eco
        else -> R.string.prof_custom
    })

    // ========================================================== atualização
    /** Procura uma versão mais nova do app nas releases do GitHub. */
    private fun verificarAtualizacao() {
        thread(isDaemon = true) {
            val nova = try {
                val c = URL("https://api.github.com/repos/parceiros-beep/segunda-tela/releases?per_page=10")
                    .openConnection() as HttpURLConnection
                c.connectTimeout = 3000; c.readTimeout = 3000
                c.setRequestProperty("Accept", "application/vnd.github+json")
                val arr = JSONArray(c.inputStream.bufferedReader().readText())
                c.disconnect()
                var melhor: String? = null
                for (i in 0 until arr.length()) {
                    val tag = arr.getJSONObject(i).optString("tag_name")
                    if (!Regex("v\\d+(\\.\\d+)+").matches(tag)) continue
                    if (melhor == null || comparar(tag.substring(1), melhor.substring(1)) > 0) melhor = tag
                }
                melhor?.substring(1)?.takeIf { comparar(it, versaoInstalada()) > 0 }
            } catch (_: Exception) { null }
            if (nova != null) runOnUiThread {
                b.lblAtualizar.text = getString(R.string.update_available, nova)
                b.lblAtualizar.visibility = View.VISIBLE
            }
        }
    }

    private fun versaoInstalada(): String =
        packageManager.getPackageInfo(packageName, 0).versionName ?: "0"

    private fun comparar(va: String, vb: String): Int {
        val x = va.split(".").map { it.toIntOrNull() ?: 0 }
        val y = vb.split(".").map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) {
            val d = x.getOrElse(i) { 0 } - y.getOrElse(i) { 0 }
            if (d != 0) return d
        }
        return 0
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

        val horizontal = Conexao.horizontal(this, aj)
        val p = Conexao.parametros(this, aj, host, horizontal)
        val abrir = Intent(this, ViewerActivity::class.java)
            .putExtra("host", host)
            .putExtra("port", aj.porta)
            .putExtra("path", Conexao.caminho(aj, p, aj.pin))
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
