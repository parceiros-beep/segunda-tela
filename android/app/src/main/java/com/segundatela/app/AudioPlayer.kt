package com.segundatela.app

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.InputStream
import java.net.InetSocketAddress
import java.net.Socket

/** Toca o som do PC (PCM 16 bits, 48 kHz, estéreo) vindo de GET /audio. */
class AudioPlayer(
    private val host: String,
    private val port: Int,
    private val pin: String
) {
    @Volatile private var ativo = false
    private var th: Thread? = null
    @Volatile private var sock: Socket? = null
    /** Chamado (fora da thread principal) quando o PC não tem o módulo de som. */
    var aoErro: ((String) -> Unit)? = null

    fun start() {
        if (ativo) return
        ativo = true
        th = Thread({ loop() }, "som").apply { isDaemon = true; start() }
    }

    fun stop() {
        ativo = false
        try { sock?.close() } catch (_: Exception) {}
        th?.interrupt()
        th = null
    }

    private fun loop() {
        var espera = 1000L
        while (ativo) {
            var track: AudioTrack? = null
            try {
                val s = Socket().apply {
                    tcpNoDelay = true
                    connect(InetSocketAddress(this@AudioPlayer.host, this@AudioPlayer.port), 4000)
                }
                sock = s
                val path = "/audio" + if (pin.isNotEmpty()) "?pin=$pin" else ""
                s.getOutputStream().apply {
                    write("GET $path HTTP/1.1\r\nHost: ${this@AudioPlayer.host}\r\n\r\n"
                        .toByteArray(Charsets.ISO_8859_1))
                    flush()
                }
                val bruto = BufferedInputStream(s.getInputStream(), 1 shl 16)
                val status = linha(bruto) ?: throw RuntimeException("sem resposta")
                if (status.contains(" 503")) {
                    ativo = false
                    aoErro?.invoke("O servidor do PC está sem o módulo de som.")
                    return
                }
                if (!status.contains(" 200")) throw RuntimeException(status)
                while (true) {
                    val l = linha(bruto) ?: throw RuntimeException("conexão encerrada")
                    if (l.isEmpty()) break
                }
                val minimo = AudioTrack.getMinBufferSize(48000,
                    AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT)
                track = AudioTrack.Builder()
                    .setAudioAttributes(AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
                    .setAudioFormat(AudioFormat.Builder()
                        .setSampleRate(48000)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build())
                    .setBufferSizeInBytes(maxOf(minimo * 2, 9600))
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY)
                    .build()
                track.play()
                espera = 1000L
                val entrada = DataInputStream(bruto)
                val buf = ByteArray(1920) // 10 ms
                while (ativo) {
                    // Mais de 150 ms acumulados? Descarta o excesso para não atrasar.
                    val fila = bruto.available()
                    if (fila > 28800) pular(bruto, fila - 3840)
                    entrada.readFully(buf)
                    track.write(buf, 0, buf.size)
                }
            } catch (_: Exception) {
            } finally {
                try { track?.release() } catch (_: Exception) {}
                try { sock?.close() } catch (_: Exception) {}
            }
            if (!ativo) break
            try { Thread.sleep(espera) } catch (_: InterruptedException) { break }
            espera = (espera * 2).coerceAtMost(5000L)
        }
    }

    /** Pula bytes mantendo o alinhamento de 4 bytes por amostra estéreo. */
    private fun pular(inp: InputStream, n: Int) {
        var restante = (n / 4 * 4).toLong()
        while (restante > 0) {
            val p = inp.skip(restante)
            if (p <= 0) break
            restante -= p
        }
        while (restante > 0 && inp.read() >= 0) restante--
    }

    private fun linha(inp: InputStream): String? {
        val sb = StringBuilder()
        while (true) {
            val b = inp.read()
            if (b == -1) return if (sb.isEmpty()) null else sb.toString()
            if (b == '\n'.code) return sb.toString().trimEnd('\r')
            sb.append(b.toChar())
        }
    }
}
