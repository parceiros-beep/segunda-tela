package com.segundatela.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Rect
import android.net.Uri
import android.util.AttributeSet
import android.view.SurfaceHolder
import android.view.SurfaceView
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Visualizador MJPEG otimizado para baixa latência:
 *  - conexão via socket cru com TCP_NODELAY (sem buffering do HttpURLConnection);
 *  - decode em RGB_565 + reuso de bitmap (menos CPU/memória);
 *  - descarte de quadros atrasados: se já chegou um quadro mais novo, pula o
 *    antigo para não acumular atraso.
 */
class MjpegView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyle: Int = 0
) : SurfaceView(context, attrs, defStyle), SurfaceHolder.Callback, Tela {

    interface Listener {
        fun onConnected()
        fun onDisconnected(reason: String)
        fun onStats(fps: Double)
    }

    var listener: Listener? = null
    private var url: String = ""
    @Volatile private var running = false
    private var worker: Thread? = null

    // Retângulo onde a imagem foi desenhada (para mapear toque -> tela do PC).
    @Volatile private var drawLeft = 0
    @Volatile private var drawTop = 0
    @Volatile private var drawW = 0
    @Volatile private var drawH = 0

    /** Converte uma coordenada do toque (px na view) em (x,y) normalizado 0..1
     *  dentro da imagem; null se o toque caiu fora da imagem (nas barras). */
    override fun toImage(px: Float, py: Float): Pair<Float, Float>? {
        val w = drawW; val h = drawH
        if (w <= 0 || h <= 0) return null
        val nx = (px - drawLeft) / w
        val ny = (py - drawTop) / h
        if (nx < 0f || nx > 1f || ny < 0f || ny > 1f) return null
        return nx to ny
    }
    private val bmpOptions = BitmapFactory.Options().apply {
        inPreferredConfig = Bitmap.Config.RGB_565
    }
    private var reuse: Bitmap? = null

    init { holder.addCallback(this) }

    fun start(streamUrl: String) {
        url = streamUrl
        if (running) return
        running = true
        worker = Thread { loop() }.apply { isDaemon = true; start() }
    }

    fun stop() {
        running = false
        worker?.interrupt()
        worker = null
    }

    override fun surfaceCreated(holder: SurfaceHolder) {}
    override fun surfaceChanged(holder: SurfaceHolder, f: Int, w: Int, h: Int) {}
    override fun surfaceDestroyed(holder: SurfaceHolder) {}

    private fun loop() {
        var backoff = 500L
        while (running) {
            var socket: Socket? = null
            try {
                val uri = Uri.parse(url)
                val host = uri.host ?: throw RuntimeException("URL inválida")
                val port = if (uri.port > 0) uri.port else 80
                val path = (uri.encodedPath ?: "/") +
                    (uri.encodedQuery?.let { "?$it" } ?: "")

                socket = Socket().apply {
                    tcpNoDelay = true                 // latência: envia já
                    receiveBufferSize = 256 * 1024
                    connect(InetSocketAddress(host, port), 4000)
                    soTimeout = 8000
                }
                val out = socket.getOutputStream()
                val req = "GET $path HTTP/1.1\r\nHost: $host\r\n" +
                    "Connection: keep-alive\r\nAccept: */*\r\n\r\n"
                out.write(req.toByteArray(Charsets.ISO_8859_1))
                out.flush()

                val input = BufferedInputStream(socket.getInputStream(), 256 * 1024)
                val status = readLine(input)
                if (status == null || !status.contains(" 200")) {
                    throw RuntimeException(status?.substringAfter(" ") ?: "sem resposta")
                }
                // Consome cabeçalhos até a linha em branco.
                while (true) {
                    val line = readLine(input) ?: throw RuntimeException("conexão encerrada")
                    if (line.isEmpty()) break
                }

                post { listener?.onConnected() }
                backoff = 500L
                readMjpeg(input)
            } catch (e: InterruptedException) {
                break
            } catch (e: Exception) {
                post { listener?.onDisconnected(e.message ?: "erro de conexão") }
                try { Thread.sleep(backoff) } catch (_: InterruptedException) { break }
                backoff = (backoff * 2).coerceAtMost(4000L)
            } finally {
                try { socket?.close() } catch (_: Exception) {}
            }
        }
    }

    private fun readLine(input: InputStream): String? {
        val sb = StringBuilder()
        while (true) {
            val b = input.read()
            if (b == -1) return if (sb.isEmpty()) null else sb.toString()
            if (b == '\n'.code) return sb.toString().trimEnd('\r')
            sb.append(b.toChar())
        }
    }

    private fun readMjpeg(input: InputStream) {
        val buffer = ByteArrayOutputStream(256 * 1024)
        var prev = -1
        var inImage = false
        var frames = 0
        var tWindow = System.currentTimeMillis()

        while (running) {
            val b = input.read()
            if (b == -1) throw RuntimeException("stream encerrado")
            if (!inImage) {
                if (prev == 0xFF && b == 0xD8) {
                    inImage = true
                    buffer.reset()
                    buffer.write(0xFF); buffer.write(0xD8)
                }
                prev = b
            } else {
                buffer.write(b)
                if (prev == 0xFF && b == 0xD9) {
                    // Descarte de atraso: se já há outro quadro completo
                    // esperando, não decodifica este (reduz latência).
                    val stale = input.available() > 8 * 1024
                    if (!stale) {
                        drawFrame(buffer.toByteArray())
                    }
                    inImage = false
                    prev = -1
                    frames++
                    val now = System.currentTimeMillis()
                    if (now - tWindow >= 1000) {
                        val fps = frames * 1000.0 / (now - tWindow)
                        post { listener?.onStats(fps) }
                        frames = 0; tWindow = now
                    }
                } else {
                    prev = b
                }
            }
        }
    }

    private fun drawFrame(jpeg: ByteArray) {
        try {
            bmpOptions.inMutable = true
            bmpOptions.inBitmap = reuse
            val bmp = try {
                BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size, bmpOptions)
            } catch (e: IllegalArgumentException) {
                bmpOptions.inBitmap = null
                BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size, bmpOptions)
            } ?: return
            reuse = bmp
            val canvas = holder.lockCanvas() ?: return
            try {
                canvas.drawColor(Color.BLACK)
                val vw = canvas.width.toFloat()
                val vh = canvas.height.toFloat()
                val bw = bmp.width.toFloat()
                val bh = bmp.height.toFloat()
                val scale = minOf(vw / bw, vh / bh)
                val dw = (bw * scale).toInt()
                val dh = (bh * scale).toInt()
                val left = ((vw - dw) / 2).toInt()
                val top = ((vh - dh) / 2).toInt()
                drawLeft = left; drawTop = top; drawW = dw; drawH = dh
                canvas.drawBitmap(bmp, null, Rect(left, top, left + dw, top + dh), null)
            } finally {
                holder.unlockCanvasAndPost(canvas)
            }
        } catch (_: Exception) {
        }
    }
}
