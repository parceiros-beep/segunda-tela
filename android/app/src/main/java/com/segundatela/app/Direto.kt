package com.segundatela.app

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier
import android.os.Build

/**
 * Conexão direta: entra na rede Wi‑Fi criada pelo PC (hotspot do Windows)
 * e prende o app nela, sem roteador no meio (Android 10 ou mais novo).
 */
object Direto {
    const val IP_PC = "192.168.137.1"
    private var callback: ConnectivityManager.NetworkCallback? = null
    @Volatile var ativo = false
        private set

    /** As funções de retorno chegam fora da thread principal. */
    fun conectar(ctx: Context, ssid: String, senha: String,
                 aoConectar: () -> Unit, aoFalhar: (String) -> Unit) {
        if (Build.VERSION.SDK_INT < 29) {
            aoFalhar(ctx.getString(R.string.direct_old_android, ssid, senha))
            return
        }
        val app = ctx.applicationContext
        val cm = app.getSystemService(ConnectivityManager::class.java)
        sair(app)
        val spec = WifiNetworkSpecifier.Builder()
            .setSsid(ssid)
            .setWpa2Passphrase(senha)
            .build()
        val pedido = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(spec)
            .build()
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                // Todo o tráfego do app passa a usar a rede do PC.
                cm.bindProcessToNetwork(network)
                ativo = true
                aoConectar()
            }

            override fun onUnavailable() {
                aoFalhar(app.getString(R.string.direct_failed, ssid))
            }

            override fun onLost(network: Network) {
                cm.bindProcessToNetwork(null)
                ativo = false
            }
        }
        callback = cb
        cm.requestNetwork(pedido, cb, 60_000)
    }

    /** Volta para a rede normal do tablet. */
    fun sair(ctx: Context) {
        val cm = ctx.applicationContext.getSystemService(ConnectivityManager::class.java)
        callback?.let { try { cm.unregisterNetworkCallback(it) } catch (_: Exception) {} }
        callback = null
        cm.bindProcessToNetwork(null)
        ativo = false
    }
}
