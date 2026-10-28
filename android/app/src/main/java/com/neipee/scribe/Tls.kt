package com.neipee.scribe

import android.net.http.SslCertificate
import android.os.Build
import java.io.IOException
import java.net.ConnectException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NoRouteToHostException
import java.net.Socket
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509TrustManager

/**
 * Confiance dans le certificat auto-signé du PC, par épinglage de son empreinte SHA-256.
 *
 * Premier raccordement : on lit le certificat présenté par le PC sans lui envoyer aucune donnée,
 * on affiche son empreinte, et l'utilisateur la compare à celle affichée dans la console du PC.
 * Ensuite, seul un certificat ayant exactement cette empreinte est accepté. Aucun certificat
 * n'est jamais accepté « en aveugle ».
 */
object Tls {

    private const val TIMEOUT_MS = 6000

    sealed class Access {
        object Ok : Access()
        /** Le PC présente un autre certificat que celui vérifié par l'utilisateur. */
        object CertChanged : Access()
        class Failure(val message: String) : Access()
    }

    class NotLocalException : IOException("adresse hors du réseau local")

    /** Le serveur a présenté un certificat dont l'empreinte diffère de l'empreinte épinglée. */
    private class PinMismatchException : CertificateException("empreinte différente")

    fun sha256Fingerprint(der: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(der).joinToString(":") { "%02X".format(it) }

    /** Même format que la console du PC, coupé en 4 lignes de 8 octets pour la comparaison. */
    fun forDisplay(fingerprint: String): String =
        fingerprint.split(':').chunked(8).joinToString("\n") { it.joinToString(":") }

    /** Empreinte du certificat que la WebView a reçu (onReceivedSslError). */
    fun fingerprintOf(certificate: SslCertificate?): String? {
        if (certificate == null) return null
        val der = if (Build.VERSION.SDK_INT >= 29) {
            certificate.x509Certificate?.encoded
        } else {
            SslCertificate.saveState(certificate).getByteArray("x509-certificate")
        }
        return der?.let { sha256Fingerprint(it) }
    }

    /** Résout l'hôte et refuse toute adresse qui n'est pas sur le réseau local. */
    fun resolveLocal(address: ServerAddress): InetAddress {
        val all = InetAddress.getAllByName(address.host)
        if (all.isEmpty() || !all.all { ServerAddress.isLocal(it) }) throw NotLocalException()
        return all.first()
    }

    /**
     * Lit l'empreinte du certificat présenté par le PC. La poignée de main TLS est
     * volontairement interrompue dès réception du certificat : aucune donnée (ni jeton)
     * n'est envoyée à un serveur non encore vérifié.
     */
    fun fetchFingerprint(address: ServerAddress): String {
        val ip = resolveLocal(address)
        val capture = CapturingTrustManager()
        val context = SSLContext.getInstance("TLS").apply { init(null, arrayOf(capture), null) }
        Socket().use { raw ->
            raw.connect(InetSocketAddress(ip, address.port), TIMEOUT_MS)
            raw.soTimeout = TIMEOUT_MS
            val ssl = context.socketFactory.createSocket(raw, address.host, address.port, false) as SSLSocket
            try {
                ssl.startHandshake()
            } catch (expected: IOException) {
                // Interruption voulue par CapturingTrustManager (ou serveur qui ne parle pas TLS).
            } finally {
                ssl.close()
            }
        }
        return capture.captured ?: throw SSLException("aucun certificat reçu")
    }

    /** Vérifie, avec le certificat épinglé, que le PC répond et accepte le jeton. */
    fun checkAccess(address: ServerAddress, pinnedFingerprint: String): Access {
        try {
            resolveLocal(address)
        } catch (e: IOException) {
            return Access.Failure(describe(e, address))
        }
        val context = SSLContext.getInstance("TLS").apply {
            init(null, arrayOf(PinnedTrustManager(pinnedFingerprint)), null)
        }
        val connection = URL(address.statusUrl).openConnection() as HttpsURLConnection
        connection.sslSocketFactory = context.socketFactory
        // Le certificat n'est pas émis par une autorité : la vérification classique du nom
        // d'hôte est remplacée par l'épinglage de l'empreinte exacte (PinnedTrustManager),
        // et la connexion reste limitée à l'hôte saisi par l'utilisateur.
        connection.hostnameVerifier = HostnameVerifier { hostname, _ ->
            hostname.removePrefix("[").removeSuffix("]").equals(address.host, ignoreCase = true)
        }
        connection.connectTimeout = TIMEOUT_MS
        connection.readTimeout = TIMEOUT_MS
        connection.instanceFollowRedirects = false
        connection.useCaches = false
        return try {
            val code = connection.responseCode
            if (code == 200) {
                Access.Ok
            } else {
                val body = (connection.errorStream ?: connection.inputStream)
                    ?.use { it.readBytes().toString(Charsets.UTF_8).take(300) } ?: ""
                when {
                    code == 403 && body.contains("Hôte") -> Access.Failure(
                        "Le PC refuse cette adresse. Utilisez exactement une des adresses IP " +
                            "affichées dans la console du PC.")
                    code == 403 -> Access.Failure(TOKEN_REFUSED)
                    else -> Access.Failure("Réponse inattendue du PC (code HTTP $code).")
                }
            }
        } catch (e: IOException) {
            if (hasCause<PinMismatchException>(e)) Access.CertChanged else Access.Failure(describe(e, address))
        } finally {
            connection.disconnect()
        }
    }

    const val TOKEN_REFUSED = "Jeton refusé par le PC. Le jeton change à chaque lancement du PC : " +
        "recopiez l'adresse complète affichée dans sa console (…/?t=…)."

    fun unreachable(address: ServerAddress) =
        "PC injoignable à l'adresse ${address.display}. Vérifiez que le PC est allumé, que Scribe y " +
            "est lancé avec « python run.py --lan », que le téléphone est sur le même réseau Wi-Fi, " +
            "et que le pare-feu Windows autorise Python."

    /** Message lisible pour une erreur réseau. */
    fun describe(error: Throwable, address: ServerAddress): String = when {
        hasCause<NotLocalException>(error) ->
            "Cette adresse n'est pas sur le réseau local. Par sécurité, Scribe ne se connecte qu'à un PC " +
                "du même réseau (adresses en 192.168.x.x, 10.x.x.x ou 172.16 à 31.x.x)."
        hasCause<UnknownHostException>(error) ->
            "Nom de PC introuvable (${address.host}). Utilisez plutôt l'adresse IP affichée par le PC."
        hasCause<ConnectException>(error) || hasCause<SocketTimeoutException>(error) ||
            hasCause<NoRouteToHostException>(error) -> unreachable(address)
        hasCause<SSLException>(error) ->
            "Le PC répond, mais pas en HTTPS. Lancez Scribe sur le PC avec « python run.py --lan »."
        else -> "Connexion au PC impossible : ${error.message ?: error.javaClass.simpleName}"
    }

    private inline fun <reified T : Throwable> hasCause(error: Throwable): Boolean {
        var current: Throwable? = error
        while (current != null) {
            if (current is T) return true
            current = current.cause
        }
        return false
    }

    /** Ne fait jamais confiance : sert uniquement à lire l'empreinte pour la montrer à l'utilisateur. */
    private class CapturingTrustManager : X509TrustManager {
        @Volatile
        var captured: String? = null

        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
            chain.firstOrNull()?.let { captured = sha256Fingerprint(it.encoded) }
            throw CertificateException("certificat lu pour vérification par l'utilisateur, connexion interrompue")
        }

        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
            throw CertificateException("non utilisé")
        }

        override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
    }

    /** N'accepte que le certificat dont l'empreinte SHA-256 a été vérifiée par l'utilisateur. */
    private class PinnedTrustManager(private val expected: String) : X509TrustManager {
        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
            val leaf = chain.firstOrNull() ?: throw CertificateException("aucun certificat")
            if (sha256Fingerprint(leaf.encoded) != expected) throw PinMismatchException()
        }

        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
            throw CertificateException("non utilisé")
        }

        override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
    }
}
