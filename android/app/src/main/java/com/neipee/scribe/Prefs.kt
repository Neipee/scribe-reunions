package com.neipee.scribe

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import android.view.View
import android.view.WindowInsets

/**
 * Stockage privé de l'appli (exclu des sauvegardes, voir le manifeste) :
 *   address           dernière adresse saisie
 *   token             dernier jeton accepté par le PC
 *   pin:<hôte>:<port> empreinte SHA-256 vérifiée par l'utilisateur, format AB:CD:…
 */
object Prefs {
    private const val FILE = "scribe"
    const val ADDRESS = "address"
    const val TOKEN = "token"
    private const val PIN_PREFIX = "pin:"

    fun of(context: Context): SharedPreferences = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun pinKey(address: ServerAddress) = "$PIN_PREFIX${address.host}:${address.port}"

    fun pins(prefs: SharedPreferences): List<Pair<String, String>> =
        prefs.all.entries
            .filter { it.key.startsWith(PIN_PREFIX) && it.value is String }
            .map { it.key.removePrefix(PIN_PREFIX) to it.value as String }
            .sortedBy { it.first }

    fun forgetPins(prefs: SharedPreferences) {
        val editor = prefs.edit()
        prefs.all.keys.filter { it.startsWith(PIN_PREFIX) }.forEach { editor.remove(it) }
        editor.apply()
    }
}

/** Android 15 affiche les applis bord à bord : on réserve la place des barres système et du clavier. */
object SystemBars {
    fun pad(view: View) {
        if (Build.VERSION.SDK_INT < 35) return
        val left = view.paddingLeft
        val top = view.paddingTop
        val right = view.paddingRight
        val bottom = view.paddingBottom
        view.setOnApplyWindowInsetsListener { v, insets ->
            val bars = insets.getInsets(
                WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime()
            )
            v.setPadding(left + bars.left, top + bars.top, right + bars.right, bottom + bars.bottom)
            insets
        }
    }
}
