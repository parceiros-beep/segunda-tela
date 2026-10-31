package com.segundatela.app

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager

/**
 * Lê informações da rede Wi-Fi (banda e velocidade do link) e sugere um
 * bitrate adequado — base do modo "Auto (otimizar)".
 *
 * Observação honesta: um app Android não força a banda 2.4/5/6 GHz (isso é do
 * sistema/roteador). O que fazemos é DETECTAR a banda e a velocidade do link e
 * ADAPTAR o streaming para o melhor desempenho possível sem travar.
 */
object NetInfo {

    data class Status(
        val isWifi: Boolean,
        val band: String,        // "2,4 GHz", "5 GHz", "6 GHz" ou "—"
        val linkMbps: Int,       // velocidade negociada do link (0 se desconhecida)
        val suggestedBitrate: Int,
        val suggestedFps: Int
    )

    fun read(context: Context): Status {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = cm.activeNetwork?.let { cm.getNetworkCapabilities(it) }
        val isWifi = caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true

        var band = "—"
        var linkMbps = 0
        try {
            val wm = context.applicationContext
                .getSystemService(Context.WIFI_SERVICE) as WifiManager
            @Suppress("DEPRECATION")
            val info = wm.connectionInfo
            if (info != null && info.networkId != -1) {
                val freq = info.frequency  // MHz
                band = when {
                    freq in 2300..2600 -> "2,4 GHz"
                    freq in 4900..5900 -> "5 GHz"
                    freq in 5925..7125 -> "6 GHz"
                    else -> "—"
                }
                linkMbps = info.linkSpeed.coerceAtLeast(0)  // Mbps
            }
        } catch (_: Exception) {}

        // Sugestão: ~25% do link, limitado a 5..40 Mbps. Sem link conhecido, 20.
        val suggestedBitrate = when {
            linkMbps <= 0 -> 20
            else -> (linkMbps * 0.25).toInt().coerceIn(5, 40)
        }
        // FPS: banda alta permite mais quadros.
        val suggestedFps = when {
            band == "5 GHz" || band == "6 GHz" -> 30
            band == "2,4 GHz" -> 20
            linkMbps >= 150 -> 30
            else -> 20
        }

        return Status(isWifi, band, linkMbps, suggestedBitrate, suggestedFps)
    }

    fun describe(s: Status): String {
        if (!s.isWifi && s.linkMbps == 0 && s.band == "—") {
            return "Rede: cabo/USB ou outra conexão"
        }
        val link = if (s.linkMbps > 0) " · link ${s.linkMbps} Mbps" else ""
        val banda = if (s.band != "—") "Wi‑Fi ${s.band}" else "Wi‑Fi"
        return "Rede: $banda$link"
    }
}
