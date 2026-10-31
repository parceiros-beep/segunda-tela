package com.segundatela.app

import android.content.Context
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

/** Blocos visuais no estilo One UI, usados nas telas de ajuste. */
object Linhas {

    fun dp(ctx: Context, v: Int) = (v * ctx.resources.displayMetrics.density).toInt()

    fun texto(ctx: Context, t: String, sp: Float, cor: Int) = TextView(ctx).apply {
        text = t
        textSize = sp
        setTextColor(ctx.getColor(cor))
    }

    /** Divisória entre linhas do mesmo cartão, recuada nas laterais. */
    fun divisor(ctx: Context, pai: LinearLayout) {
        if (pai.childCount == 0) return
        pai.addView(View(ctx).apply {
            setBackgroundColor(ctx.getColor(R.color.divider))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(ctx, 1)).apply {
                marginStart = dp(ctx, 20); marginEnd = dp(ctx, 20)
            }
        })
    }

    /** Linha de cartão; tocar nela pode abrir uma escolha. */
    fun linha(ctx: Context, pai: LinearLayout, vertical: Boolean): LinearLayout {
        divisor(ctx, pai)
        val row = LinearLayout(ctx).apply {
            orientation = if (vertical) LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            minimumHeight = dp(ctx, 64)
            setPadding(dp(ctx, 20), dp(ctx, 14), dp(ctx, 20), dp(ctx, 14))
            setBackgroundResource(R.drawable.row_bg)
        }
        pai.addView(row)
        return row
    }

    /** Explicação curta embaixo do título: o que a opção faz e a recomendação. */
    fun explica(ctx: Context, row: LinearLayout, res: Int?) {
        if (res == null) return
        row.addView(texto(ctx, ctx.getString(res), 13f, R.color.text_muted).apply {
            setPadding(0, dp(ctx, 6), 0, 0)
        })
    }
}
