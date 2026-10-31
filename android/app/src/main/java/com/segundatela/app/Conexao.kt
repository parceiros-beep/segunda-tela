package com.segundatela.app

import android.content.Context
import android.content.res.Configuration
import android.os.Build
import android.util.DisplayMetrics

/**
 * Cálculo da transmissão (tamanho, fps, bitrate e o caminho do stream).
 * Usado ao conectar e ao reiniciar a transmissão com os ajustes ao vivo.
 */
object Conexao {

    class Parametros(
        val w: Int, val h: Int, val escala: Int, val fps: Int, val mbps: Int
    )

    fun par(v: Int) = v / 2 * 2

    /** Tamanho real da tela do tablet (maior lado, menor lado). */
    fun nativo(ctx: Context): Pair<Int, Int> {
        val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as android.view.WindowManager
        return if (Build.VERSION.SDK_INT >= 30) {
            val r = wm.maximumWindowMetrics.bounds
            r.width() to r.height()
        } else {
            val m = DisplayMetrics()
            @Suppress("DEPRECATION")
            wm.defaultDisplay.getRealMetrics(m)
            m.widthPixels to m.heightPixels
        }
    }

    /** Orientação da sessão: "auto" acompanha o tablet no momento. */
    fun horizontal(ctx: Context, aj: Ajustes): Boolean = when (aj.orientacao) {
        "horizontal" -> true
        "vertical" -> false
        else -> ctx.resources.configuration.orientation != Configuration.ORIENTATION_PORTRAIT
    }

    /** Automático: 60 fps com cabo USB ou Wi‑Fi 5/6 GHz rápido; senão 30. */
    fun fpsAutomatico(ctx: Context): Int {
        val st = try { NetInfo.read(ctx) } catch (_: Exception) { return 30 }
        return if (st.band == "5 GHz" || st.band == "6 GHz" || st.linkMbps >= 200) 60 else 30
    }

    fun parametros(ctx: Context, aj: Ajustes, host: String, horizontal: Boolean): Parametros {
        val (nw, nh) = nativo(ctx)
        val maior = maxOf(nw, nh); val menor = minOf(nw, nh)
        val w = par((if (horizontal) maior else menor) * aj.resolucao / 100)
        val h = par((if (horizontal) menor else maior) * aj.resolucao / 100)
        val escala = if (aj.escala > 0) aj.escala else Ajustes.escalaAuto(maxOf(w, h))
        // Cabo USB sempre 60 no automático; Wi‑Fi conforme a banda.
        val fps = if (aj.fps > 0) aj.fps
            else if (host == "127.0.0.1") 60 else fpsAutomatico(ctx)
        val mbps = if (aj.mbps > 0) aj.mbps else {
            // ~0,1 bit por pixel; limitado pela velocidade do Wi‑Fi.
            val bpp = if (aj.codec == "h265") 14_000_000L else 10_000_000L
            val ideal = (w.toLong() * h * fps / bpp).toInt().coerceIn(6, 60)
            if (host == "127.0.0.1") ideal else {
                val link = try { NetInfo.read(ctx).linkMbps } catch (_: Exception) { 0 }
                if (link > 0) minOf(ideal, maxOf(6, link * 2 / 5)) else ideal
            }
        }
        return Parametros(w, h, escala, fps, mbps)
    }

    /** Texto do caminho HTTP que o tablet pede ao servidor. */
    fun caminho(aj: Ajustes, p: Parametros, pin: String): String {
        val s = StringBuilder()
        if (aj.compat) {
            s.append("/stream?fps=${minOf(p.fps, 30)}&quality=${aj.jpeg}")
        } else {
            s.append("/video?fps=${p.fps}&kbps=${p.mbps * 1000}&codec=${aj.codec}")
            s.append("&taxa=${aj.taxa}&cq=${aj.cq}&vel=${aj.velocidade}")
            s.append("&gop=${aj.gop}&intra=${if (aj.intra) 1 else 0}")
        }
        s.append("&cursor=${if (aj.cursor) 1 else 0}")
        s.append("&w=${p.w}&h=${p.h}&modo=${aj.modo}&lado=${aj.lado}&escala=${p.escala}")
        if (pin.isNotEmpty()) s.append("&pin=$pin")
        return s.toString()
    }
}
