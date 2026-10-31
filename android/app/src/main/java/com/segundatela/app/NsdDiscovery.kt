package com.segundatela.app

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper

/**
 * Descoberta automática de servidores "Segunda Tela" na rede local via mDNS
 * (NSD). Reporta host:porta encontrados na thread principal.
 */
class NsdDiscovery(context: Context) {

    data class Device(val name: String, val host: String, val port: Int)

    interface Listener {
        fun onFound(device: Device)
    }

    private val nsd = context.applicationContext
        .getSystemService(Context.NSD_SERVICE) as NsdManager
    private val ui = Handler(Looper.getMainLooper())
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var active = false
    var listener: Listener? = null

    private val serviceType = "_segundatela._tcp."

    fun start() {
        if (active) return
        val l = object : NsdManager.DiscoveryListener {
            override fun onStartDiscoveryFailed(s: String?, e: Int) {}
            override fun onStopDiscoveryFailed(s: String?, e: Int) {}
            override fun onDiscoveryStarted(s: String?) {}
            override fun onDiscoveryStopped(s: String?) {}

            override fun onServiceFound(info: NsdServiceInfo) {
                try {
                    resolve(info)
                } catch (_: Exception) {}
            }

            override fun onServiceLost(info: NsdServiceInfo?) {}
        }
        discoveryListener = l
        try {
            nsd.discoverServices(serviceType, NsdManager.PROTOCOL_DNS_SD, l)
            active = true
        } catch (_: Exception) {}
    }

    private fun resolve(info: NsdServiceInfo) {
        nsd.resolveService(info, object : NsdManager.ResolveListener {
            override fun onResolveFailed(s: NsdServiceInfo?, e: Int) {}
            override fun onServiceResolved(s: NsdServiceInfo) {
                val host = s.host?.hostAddress ?: return
                val dev = Device(s.serviceName ?: "PC", host, s.port)
                ui.post { listener?.onFound(dev) }
            }
        })
    }

    fun stop() {
        try {
            discoveryListener?.let { nsd.stopServiceDiscovery(it) }
        } catch (_: Exception) {}
        discoveryListener = null
        active = false
    }
}
