package com.segundatela.app

import android.os.Handler
import android.os.HandlerThread
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * Envia eventos de entrada (toque, caneta, mouse e teclado) do tablet para o
 * servidor do PC.
 *
 * Mantém um socket keep-alive separado do stream de vídeo e manda uma linha de
 * texto por evento (POST /input), com TCP_NODELAY para latência baixa. As
 * coordenadas são normalizadas (0..1) em relação à IMAGEM exibida; o servidor
 * converte para a área do monitor que está transmitindo.
 */
class InputSender(
    private val host: String,
    private val port: Int,
    private val pin: String
) {
    private val fila = ConcurrentLinkedQueue<String>()
    @Volatile private var ativo = false
    private var th: HandlerThread? = null
    private var handler: Handler? = null
    private var socket: Socket? = null
    private var out: OutputStream? = null

    fun start() {
        if (ativo) return
        ativo = true
        th = HandlerThread("input").also { it.start() }
        handler = Handler(th!!.looper)
        handler?.post { conectar() }
    }

    fun stop() {
        ativo = false
        handler?.post {
            try { socket?.close() } catch (_: Exception) {}
        }
        th?.quitSafely()
        th = null; handler = null
    }

    private fun conectar() {
        if (!ativo) return
        try {
            val s = Socket().apply {
                tcpNoDelay = true
                connect(InetSocketAddress(this@InputSender.host, this@InputSender.port), 4000)
            }
            val o = s.getOutputStream()
            val req = "POST /input HTTP/1.1\r\nHost: $host\r\n" +
                "Content-Type: text/plain\r\nConnection: keep-alive\r\n" +
                "X-Stream: input\r\n\r\n"
            o.write(req.toByteArray(Charsets.ISO_8859_1)); o.flush()
            socket = s; out = o
            lerRespostas(s)
        } catch (_: Exception) {
            if (ativo) handler?.postDelayed({ conectar() }, 1000)
        }
    }

    /** Recebe "pong <t>" do servidor e calcula o atraso de ida e volta. */
    var aoPing: ((Long) -> Unit)? = null

    private fun lerRespostas(s: Socket) {
        Thread({
            try {
                val r = s.getInputStream().bufferedReader(Charsets.UTF_8)
                while (ativo) {
                    val l = r.readLine() ?: break
                    val i = l.indexOf("pong ")
                    if (i >= 0) {
                        val t = l.substring(i + 5).trim().toLongOrNull() ?: continue
                        aoPing?.invoke(android.os.SystemClock.elapsedRealtime() - t)
                    }
                }
            } catch (_: Exception) {
            }
        }, "input-resp").apply { isDaemon = true; start() }
    }

    fun ping() = enfileira("png ${android.os.SystemClock.elapsedRealtime()}")

    // ---- API de eventos (coordenadas normalizadas 0..1) ----
    fun move(x: Float, y: Float) = enfileira("m ${f(x)} ${f(y)}")
    fun down(x: Float, y: Float) = enfileira("d ${f(x)} ${f(y)}")
    fun up(x: Float, y: Float) = enfileira("u ${f(x)} ${f(y)}")
    fun rightClick(x: Float, y: Float) = enfileira("r ${f(x)} ${f(y)}")
    fun scroll(x: Float, y: Float, dy: Int) = enfileira("s ${f(x)} ${f(y)} $dy")
    fun key(code: String) = enfileira("k $code")
    fun text(t: String) = enfileira("t " + t.replace("\n", "\\n"))
    // Touchpad: movimento relativo e cliques no ponto atual do cursor
    fun relMove(dx: Float, dy: Float) =
        enfileira(String.format(java.util.Locale.US, "rm %.5f %.5f", dx, dy))
    fun clickHere(right: Boolean) = enfileira(if (right) "cr" else "cl")
    fun wheelHere(ticks: Int) = enfileira("sw $ticks")

    fun keyDown(vk: Int) = enfileira("kd $vk")
    fun keyUp(vk: Int) = enfileira("ku $vk")

    // Toque nativo do Windows (multitoque)
    fun touch(acao: Char, id: Int, x: Float, y: Float) = enfileira("T $acao $id ${f(x)} ${f(y)}")
    fun touchMove(pontos: List<Triple<Int, Float, Float>>) {
        if (pontos.isEmpty()) return
        enfileira("TM " + pontos.joinToString(" ") { "${it.first} ${f(it.second)} ${f(it.third)}" })
    }
    fun touchReset() = enfileira("TR")

    // Caneta: estado h/d/m/u/x, pressão 0..1, inclinação em graus, botões
    fun pen(estado: Char, x: Float, y: Float, pressao: Float, tx: Float, ty: Float, botoes: Int) =
        enfileira("P $estado ${f(x)} ${f(y)} ${String.format(java.util.Locale.US, "%.3f", pressao)} " +
            "${tx.toInt()} ${ty.toInt()} $botoes")

    private fun f(v: Float) = String.format(java.util.Locale.US, "%.4f", v.coerceIn(0f, 1f))

    private fun enfileira(linha: String) {
        if (!ativo) return
        val l = if (pin.isNotEmpty()) "$linha|$pin\n" else "$linha\n"
        handler?.post { envia(l) }
    }

    private fun envia(linha: String) {
        val o = out ?: run { conectar(); return }
        try {
            o.write(linha.toByteArray(Charsets.UTF_8)); o.flush()
        } catch (_: Exception) {
            try { socket?.close() } catch (_: Exception) {}
            out = null; socket = null
            if (ativo) conectar()
        }
    }
}
