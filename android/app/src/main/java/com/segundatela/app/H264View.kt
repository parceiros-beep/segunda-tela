package com.segundatela.app

import android.content.Context
import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import android.util.AttributeSet
import android.view.SurfaceHolder
import android.view.SurfaceView
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Recebe o vídeo H.264 do servidor e decodifica por hardware (MediaCodec)
 * direto na superfície, no modo de baixa latência.
 *
 * Protocolo (GET /video): pacotes [tipo:1][tamanho:4][dados]
 *   0 = JSON {"w","h","encoder"}, 1 = quadro H.264 Annex-B, 2 = erro (texto)
 */
class H264View @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyle: Int = 0
) : SurfaceView(context, attrs, defStyle), SurfaceHolder.Callback, Tela {

    interface Listener {
        fun onConnected(info: String)
        fun onDisconnected(reason: String)
        fun onStats(fps: Double)
        fun onFatal(msg: String)
        fun onEstatisticas(e: Estatisticas) {}
    }

    /** Números de 1 segundo para o painel de estatísticas. */
    data class Estatisticas(
        val fps: Double, val mbps: Double, val decodMs: Double,
        val descartados: Int, val codec: String, val encoder: String,
        val w: Int, val h: Int
    )

    var listener: Listener? = null
    /** Mostrar sempre o quadro mais novo (descarta os atrasados). */
    @Volatile var ultimoQuadro = true
    private var host = ""
    private var port = 8080
    private var path = ""
    @Volatile private var running = false
    private var worker: Thread? = null
    @Volatile private var socket: Socket? = null

    @Volatile private var surfaceOk = CountDownLatch(1)
    private var codec: MediaCodec? = null
    private var outThread: Thread? = null
    private var codecW = 0
    private var codecH = 0
    @Volatile private var videoW = 0
    @Volatile private var videoH = 0
    @Volatile private var videoMime = MediaFormat.MIMETYPE_VIDEO_AVC
    private var codecMime = ""
    @Volatile private var encoderNome = ""
    // Estatísticas (janela de 1 s)
    @Volatile private var descartados = 0
    @Volatile private var somaDecodUs = 0L
    @Volatile private var nDecod = 0

    init { holder.addCallback(this) }

    override fun toImage(px: Float, py: Float): Pair<Float, Float>? {
        if (width <= 0 || height <= 0) return null
        return (px / width).coerceIn(0f, 1f) to (py / height).coerceIn(0f, 1f)
    }

    /** Ocupa o maior espaço possível mantendo a proporção do vídeo. */
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val pw = MeasureSpec.getSize(widthMeasureSpec)
        val ph = MeasureSpec.getSize(heightMeasureSpec)
        val vw = videoW; val vh = videoH
        if (vw <= 0 || vh <= 0 || pw <= 0 || ph <= 0) {
            setMeasuredDimension(pw, ph); return
        }
        val s = minOf(pw.toFloat() / vw, ph.toFloat() / vh)
        setMeasuredDimension((vw * s).toInt(), (vh * s).toInt())
    }

    fun start(host: String, port: Int, path: String) {
        this.host = host; this.port = port; this.path = path
        if (running) return
        running = true
        worker = Thread({ loop() }, "video").apply { isDaemon = true; start() }
    }

    fun stop() {
        running = false
        try { socket?.close() } catch (_: Exception) {}
        worker?.interrupt()
        worker = null
        liberarCodec()
    }

    override fun surfaceCreated(h: SurfaceHolder) { surfaceOk.countDown() }
    override fun surfaceChanged(h: SurfaceHolder, f: Int, w: Int, hh: Int) {}
    override fun surfaceDestroyed(h: SurfaceHolder) {
        surfaceOk = CountDownLatch(1)
        liberarCodec()
        // Reconecta: a nova sessão começa num quadro-chave (imagem limpa).
        try { socket?.close() } catch (_: Exception) {}
    }

    private fun loop() {
        var backoff = 500L
        while (running) {
            try {
                val s = Socket().apply {
                    tcpNoDelay = true
                    receiveBufferSize = 1 shl 20
                    connect(InetSocketAddress(this@H264View.host, this@H264View.port), 4000)
                    soTimeout = 0
                }
                socket = s
                val out = s.getOutputStream()
                out.write(("GET $path HTTP/1.1\r\nHost: $host\r\n" +
                    "Connection: keep-alive\r\n\r\n").toByteArray(Charsets.ISO_8859_1))
                out.flush()
                val raw = BufferedInputStream(s.getInputStream(), 1 shl 18)
                val status = readLine(raw) ?: throw RuntimeException("sem resposta")
                if (!status.contains(" 200")) {
                    val msg = status.substringAfter(" ")
                    if (status.contains(" 403")) {
                        post { listener?.onFatal("PIN incorreto") }
                        running = false
                        return
                    }
                    throw RuntimeException(msg)
                }
                while (true) {
                    val l = readLine(raw) ?: throw RuntimeException("conexão encerrada")
                    if (l.isEmpty()) break
                }
                s.soTimeout = 15000
                backoff = 500L
                lerPacotes(DataInputStream(raw))
            } catch (e: InterruptedException) {
                break
            } catch (e: Exception) {
                if (!running) break
                liberarCodec()
                val motivo = when {
                    e is java.net.ConnectException || e.message?.contains("ECONNREFUSED") == true ->
                        "o PC não respondeu em $host:$port — o Segunda Tela está aberto no PC?"
                    e is java.net.SocketTimeoutException ->
                        "sem resposta de $host:$port — mesma rede Wi‑Fi? Firewall liberado?"
                    else -> e.message ?: "erro de conexão"
                }
                post { listener?.onDisconnected(motivo) }
                try { Thread.sleep(backoff) } catch (_: InterruptedException) { break }
                backoff = (backoff * 2).coerceAtMost(4000L)
            } finally {
                try { socket?.close() } catch (_: Exception) {}
            }
        }
    }

    private fun lerPacotes(inp: DataInputStream) {
        var buf = ByteArray(1 shl 20)
        var frames = 0
        var bytes = 0L
        var janela = System.currentTimeMillis()
        while (running) {
            val tipo = inp.readUnsignedByte()
            val n = inp.readInt()
            if (n < 0 || n > 64 * 1024 * 1024) throw RuntimeException("dados inválidos")
            if (n > buf.size) buf = ByteArray(n + (n shr 1))
            inp.readFully(buf, 0, n)
            when (tipo) {
                0 -> {
                    val j = JSONObject(String(buf, 0, n, Charsets.UTF_8))
                    val w = j.optInt("w"); val h = j.optInt("h")
                    videoMime = if (j.optString("codec") == "h265")
                        MediaFormat.MIMETYPE_VIDEO_HEVC else MediaFormat.MIMETYPE_VIDEO_AVC
                    if (w != videoW || h != videoH) {
                        videoW = w; videoH = h
                        post { requestLayout() }
                    }
                    val enc = j.optString("encoder", "")
                    if (enc.isNotEmpty()) {
                        encoderNome = enc
                        val ext = if (j.optBoolean("extendido")) "Tela estendida" else "Espelhando"
                        post { listener?.onConnected("$ext · ${w}×$h · $enc") }
                    }
                }
                1 -> {
                    bytes += n
                    val c = garantirCodec() ?: continue
                    // pts = hora da chegada: na saída dá o tempo de decodificação.
                    alimentar(c, buf, n, System.nanoTime() / 1000)
                    frames++
                    val agora = System.currentTimeMillis()
                    if (agora - janela >= 1000) {
                        val dt = (agora - janela) / 1000.0
                        val fps = frames / dt
                        val e = Estatisticas(fps, bytes * 8 / dt / 1_000_000.0,
                            if (nDecod > 0) somaDecodUs / nDecod / 1000.0 else 0.0,
                            descartados,
                            if (codecMime == MediaFormat.MIMETYPE_VIDEO_HEVC) "H.265" else "H.264",
                            encoderNome, videoW, videoH)
                        somaDecodUs = 0; nDecod = 0; descartados = 0
                        post { listener?.onStats(fps); listener?.onEstatisticas(e) }
                        frames = 0; bytes = 0; janela = agora
                    }
                }
                2 -> {
                    val msg = String(buf, 0, n, Charsets.UTF_8)
                    post { listener?.onFatal(msg) }
                }
            }
        }
    }

    private fun garantirCodec(): MediaCodec? {
        val w = videoW; val h = videoH
        if (w <= 0 || h <= 0) return null
        val mime = videoMime
        codec?.let { if (w == codecW && h == codecH && mime == codecMime) return it }
        liberarCodec()
        if (!surfaceOk.await(5, TimeUnit.SECONDS)) return null
        val c = try {
            criarDecoder(mime, w, h, extras = true)
        } catch (e: Exception) {
            // Alguns decodificadores recusam as chaves de baixa latência.
            criarDecoder(mime, w, h, extras = false)
        }
        codec = c; codecW = w; codecH = h; codecMime = mime
        outThread = Thread({ saida(c) }, "video-out").apply { isDaemon = true; start() }
        return c
    }

    private fun criarDecoder(mime: String, w: Int, h: Int, extras: Boolean): MediaCodec {
        val fmt = MediaFormat.createVideoFormat(mime, w, h)
        fmt.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, w * h)
        if (extras) {
            if (Build.VERSION.SDK_INT >= 30) fmt.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
            fmt.setInteger(MediaFormat.KEY_PRIORITY, 0)
            fmt.setInteger("vendor.qti-ext-dec-low-latency.enable", 1)
            fmt.setInteger("vendor.low-latency.enable", 1)
        }
        val c = MediaCodec.createDecoderByType(mime)
        try {
            c.configure(fmt, holder.surface, null, 0)
            c.start()
        } catch (e: Exception) {
            try { c.release() } catch (_: Exception) {}
            throw e
        }
        return c
    }

    private fun alimentar(c: MediaCodec, data: ByteArray, n: Int, pts: Long) {
        try {
            var idx = -1
            for (i in 0 until 50) {
                idx = c.dequeueInputBuffer(10_000)
                if (idx >= 0 || !running) break
            }
            if (idx < 0) { descartados++; return }
            val ib = c.getInputBuffer(idx) ?: return
            ib.clear()
            ib.put(data, 0, minOf(n, ib.capacity()))
            c.queueInputBuffer(idx, 0, minOf(n, ib.capacity()), pts, 0)
        } catch (e: IllegalStateException) {
            liberarCodec()
        }
    }

    private fun saida(c: MediaCodec) {
        val info = MediaCodec.BufferInfo()
        try {
            var pendente = -1
            while (running && codec === c) {
                // Com "quadro mais recente": se já há outro pronto, pula o antigo.
                val espera = if (pendente >= 0) 0L else 20_000L
                val idx = c.dequeueOutputBuffer(info, espera)
                if (idx >= 0) {
                    val agoraUs = System.nanoTime() / 1000
                    if (info.presentationTimeUs in 1..agoraUs) {
                        somaDecodUs += agoraUs - info.presentationTimeUs; nDecod++
                    }
                    if (!ultimoQuadro) { c.releaseOutputBuffer(idx, true); continue }
                    if (pendente >= 0) { c.releaseOutputBuffer(pendente, false); descartados++ }
                    pendente = idx
                } else if (pendente >= 0) {
                    c.releaseOutputBuffer(pendente, true)
                    pendente = -1
                }
            }
        } catch (_: Exception) {
        }
    }

    @Synchronized
    private fun liberarCodec() {
        val c = codec ?: return
        codec = null; codecW = 0; codecH = 0
        try { outThread?.join(200) } catch (_: Exception) {}
        outThread = null
        try { c.stop() } catch (_: Exception) {}
        try { c.release() } catch (_: Exception) {}
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
}

/** Superfície de vídeo que sabe converter o toque em coordenada da tela do PC. */
interface Tela {
    fun toImage(px: Float, py: Float): Pair<Float, Float>?
}
