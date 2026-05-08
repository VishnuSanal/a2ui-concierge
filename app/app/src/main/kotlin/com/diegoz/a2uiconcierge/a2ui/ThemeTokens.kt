package com.diegoz.a2uiconcierge.a2ui

import org.json.JSONObject

object ThemeTokens {
    fun asJson(): String = JSONObject(
        mapOf(
            "color-bg" to "#F8F4ED",
            "color-fg" to "#1B1B1F",
            "color-accent" to "#5B6CFF",
            "color-success" to "#7AB87A",
            "radius-md" to "14px",
            "font-sans" to "Inter, system-ui, sans-serif",
            "font-serif" to "Fraunces, 'Times New Roman', serif",
        )
    ).toString()
}
