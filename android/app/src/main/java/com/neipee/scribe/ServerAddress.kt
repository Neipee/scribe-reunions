package com.neipee.scribe

import java.net.Inet6Address
import java.net.InetAddress
import java.net.URI
import java.net.URISyntaxException
import java.net.URLEncoder

/** Erreur de saisie, avec un message lisible destiné à l'utilisateur. */
class AddressException(message: String) : Exception(message)

/** Adresse du serveur Scribe sur le PC (mode `python run.py --lan`) et jeton d'accès. */
data class ServerAddress(val host: String, val port: Int, val token: String) {

    private val urlHost: String get() = if (host.contains(':')) "[$host]" else host
    private val encodedToken: String get() = URLEncoder.encode(token, "UTF-8")

    val origin: String get() = "https://$urlHost:$port"
    val display: String get() = "$urlHost:$port"
    /** Page d'accueil : le serveur lit le jeton dans `?t=` puis le pose en cookie. */
    val pageUrl: String get() = "$origin/?t=$encodedToken"
    val statusUrl: String get() = "$origin/api/status?t=$encodedToken"

    /** Vrai si l'URL a exactement la même origine (https, hôte, port) que le PC configuré. */
    fun sameOrigin(scheme: String?, otherHost: String?, otherPort: Int): Boolean {
        if (!"https".equals(scheme, ignoreCase = true) || otherHost == null) return false
        val bareHost = otherHost.removePrefix("[").removeSuffix("]")
        return bareHost.equals(host, ignoreCase = true) && (if (otherPort == -1) 443 else otherPort) == port
    }

    companion object {
        const val DEFAULT_PORT = 8765
        private val TOKEN_RE = Regex("^[A-Za-z0-9_-]{8,128}$")
        private val HOST_RE = Regex("^[A-Za-z0-9.-]{1,253}$")

        /**
         * Accepte l'adresse complète affichée par le PC (https://192.168.x.x:8765/?t=…),
         * ou une adresse seule (192.168.x.x, 192.168.x.x:8765) avec le jeton à part.
         */
        fun parse(addressInput: String, tokenInput: String): ServerAddress {
            var text = addressInput.trim()
            if (text.isEmpty()) throw AddressException("Saisissez l'adresse affichée par le PC.")
            if (!text.contains("://")) text = "https://$text"
            val uri = try {
                URI(text)
            } catch (e: URISyntaxException) {
                throw AddressException("Adresse illisible. Exemple : https://192.168.x.x:8765/?t=…")
            }
            if (!"https".equals(uri.scheme, ignoreCase = true)) {
                throw AddressException("L'adresse doit commencer par https:// : lancez le PC avec « python run.py --lan ».")
            }
            val host = uri.host?.removePrefix("[")?.removeSuffix("]")?.lowercase()
            if (host.isNullOrEmpty() || !(HOST_RE.matches(host) || host.contains(':'))) {
                throw AddressException("Adresse du PC illisible. Exemple : https://192.168.x.x:8765/?t=…")
            }
            val port = if (uri.port == -1) DEFAULT_PORT else uri.port

            val tokenFromUrl = uri.rawQuery?.split('&')
                ?.map { it.split('=', limit = 2) }
                ?.firstOrNull { it.size == 2 && it[0] == "t" }
                ?.get(1)
            val token = (tokenFromUrl ?: tokenInput).trim()
            if (token.isEmpty()) {
                throw AddressException("Jeton manquant : recopiez l'adresse complète affichée par le PC (avec ?t=…).")
            }
            if (!TOKEN_RE.matches(token)) {
                throw AddressException("Jeton illisible : il ne contient que des lettres, chiffres, « - » et « _ ».")
            }
            return ServerAddress(host, port, token)
        }

        /** Réseau local uniquement : adresses privées, lien-local, boucle locale, IPv6 ULA. */
        fun isLocal(address: InetAddress): Boolean =
            address.isSiteLocalAddress || address.isLinkLocalAddress || address.isLoopbackAddress ||
                (address is Inet6Address && (address.address[0].toInt() and 0xFE) == 0xFC)
    }
}
