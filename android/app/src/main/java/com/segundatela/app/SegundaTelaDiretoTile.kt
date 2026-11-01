package com.segundatela.app

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

/** Botão no painel rápido: conexão direta (sem roteador) na última faixa usada. */
class SegundaTelaDiretoTile : TileService() {

    private fun banda() = getSharedPreferences("segundatela", Context.MODE_PRIVATE)
        .getString("direto_banda", "5") ?: "5"

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.apply {
            state = if (Direto.ativo) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
            label = getString(R.string.tile_direct_label)
            if (Build.VERSION.SDK_INT >= 29) {
                subtitle = if (banda() == "2.4") "2,4 GHz" else "5 GHz"
            }
            updateTile()
        }
    }

    override fun onClick() {
        super.onClick()
        val intent = Intent(this, ConnectActivity::class.java)
            .putExtra("diretoAgora", banda())
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (Build.VERSION.SDK_INT >= 34) {
            val pi = PendingIntent.getActivity(this, 1, intent,
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            startActivityAndCollapse(pi)
        } else {
            @Suppress("DEPRECATION", "StartActivityAndCollapseDeprecated")
            startActivityAndCollapse(intent)
        }
    }
}
